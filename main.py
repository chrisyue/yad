#!/usr/bin/env python3

import tomllib
import threading
import time
import subprocess
from collections import deque
from pathlib import Path

import numpy as np
import miniaudio
import requests
import Quartz
import CoreFoundation

from mlx_audio.stt import load as load_model


CONFIG_PATH = Path(__file__).with_name("config.toml")
with CONFIG_PATH.open("rb") as f:
    config = tomllib.load(f)

STT_MODEL_PATH = config["stt"]["model_path"]
STT_SYS_PROMPT = config["stt"]["sys_prompt"]

ENABLE_POST_PROCESS = config["llm"]["enabled"]
LLM_URL = config["llm"]["url"]
LLM_API_KEY = config["llm"]["api_key"]
LLM_MODEL = config["llm"]["model"]
LLM_TIMEOUT = config["llm"]["timeout"]
LLM_PROMPT = config["llm"]["prompt"]

SAMPLE_RATE = config["audio"]["sample_rate"]
CHANNELS = config["audio"]["channels"]
MAX_RECORDING_SECONDS = config["audio"]["max_recording_seconds"]
MIN_RECORDING_SECONDS = config["audio"]["min_recording_seconds"]
TYPE_CHAR_DELAY = config["audio"]["type_char_delay"]

DICTATION_KEYCODE = config["hotkey"]["dictation_keycode"]

BEEP_START = config["sounds"]["start"]
BEEP_STOP = config["sounds"]["stop"]
BEEP_BUSY = config["sounds"]["busy"]


def beep(path):
    subprocess.Popen(["afplay", path])


stt_model = None
capture_device = None
recording_timer = None
processing_thread = None
audio_chunks = deque()
event_tap = None
dict_key_down = False
recording = False


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def load_models():
    global stt_model
    log(f"Loading STT model: {STT_MODEL_PATH}")
    stt_model = load_model(STT_MODEL_PATH)
    log("STT model loaded.")


def run_stt(audio):
    result = stt_model.generate(audio, use_itn=True, system_prompt=STT_SYS_PROMPT)
    if isinstance(result, str):
        return result
    if hasattr(result, "text"):
        return result.text
    if isinstance(result, dict):
        return result.get("text", "")
    return str(result)


def audio_gen():
    while True:
        data = yield
        if data:
            audio_chunks.append(np.frombuffer(data, dtype=np.float32).copy())


def start_recording():
    global recording, capture_device, recording_timer
    recording = True
    audio_chunks.clear()
    if capture_device is None:
        capture_device = miniaudio.CaptureDevice(
            input_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=CHANNELS,
            sample_rate=SAMPLE_RATE,
            buffersize_msec=50,
        )
    g = audio_gen()
    g.send(None)
    capture_device.start(g)
    recording_timer = threading.Timer(MAX_RECORDING_SECONDS, finish_recording)
    recording_timer.start()


def stop_recording():
    global recording
    recording = False
    recording_timer.cancel()
    threading.Thread(target=capture_device.stop, daemon=True).start()


def finish_recording():
    stop_recording()
    beep(BEEP_STOP)
    start_processing()


def transcribe_and_type():
    global processing_thread
    try:
        if not audio_chunks:
            log("No audio recorded.")
            return
        audio = np.concatenate(list(audio_chunks), axis=0).flatten()
        duration = len(audio) / SAMPLE_RATE
        log(f"Recorded {duration:.3f}s")
        if duration < MIN_RECORDING_SECONDS:
            log("Recording too short.")
            return
        text = run_stt(audio)
        log(f"STT: {text}")
        if ENABLE_POST_PROCESS and text:
            text = post_process(text)
        if text:
            type_text(text)
    finally:
        processing_thread = None


def start_processing():
    global processing_thread
    processing_thread = threading.Thread(target=transcribe_and_type, daemon=True)
    processing_thread.start()


def post_process(text):
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    prompt = LLM_PROMPT.strip().format(text=text)
    response = requests.post(
        LLM_URL,
        headers=headers,
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def type_text(text):
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for char in text:
        event = Quartz.CGEventCreateKeyboardEvent(source, 0, True)
        Quartz.CGEventKeyboardSetUnicodeString(event, len(char), char)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

        event = Quartz.CGEventCreateKeyboardEvent(source, 0, False)
        Quartz.CGEventKeyboardSetUnicodeString(event, len(char), char)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

        time.sleep(TYPE_CHAR_DELAY)


def keyboard_event_callback(proxy, event_type, event, refcon):
    keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
    if keycode != DICTATION_KEYCODE:
        return event

    global dict_key_down, recording
    if event_type == Quartz.kCGEventKeyDown:
        if dict_key_down:
            return None
        dict_key_down = True
        if processing_thread is not None:
            beep(BEEP_BUSY)
            return None
        beep(BEEP_START)
        start_recording()
        return None

    if event_type == Quartz.kCGEventKeyUp:
        if not dict_key_down:
            return None
        dict_key_down = False
        recording and finish_recording()
        return None

    return event


def create_event_tap():
    global event_tap
    mask = (1 << Quartz.kCGEventKeyDown) | (1 << Quartz.kCGEventKeyUp)
    event_tap = Quartz.CGEventTapCreate(
        Quartz.kCGHIDEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        mask,
        keyboard_event_callback,
        None,
    )
    if event_tap is None:
        raise RuntimeError("Failed to create event tap.")
    source = Quartz.CFMachPortCreateRunLoopSource(None, event_tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(),
        source,
        Quartz.kCFRunLoopCommonModes,
    )
    Quartz.CGEventTapEnable(event_tap, True)


def main():
    load_models()
    create_event_tap()
    log("Ready.")
    CoreFoundation.CFRunLoopRun()


if __name__ == "__main__":
    main()
