(YAD)Yet Another Dictation
==========================

就是一个利用其他更好用的本地ASR模型比如Qwen3 ASR来取代macOS内置听写功能的小工具。

我实在懒得写README，诸君看看配置文件样本`config.toml.example`，大概就知道怎么用了。

需要注意的是，此脚本需要输入监控的权限才能运行。如果你是通过命令行启动的，
那么你就需要把终端或者你常用的TTY工具的输入监控权限以及设备控制和数据访问权限打开。
获取这些权限只是为了监控你有没有按下听写键。若是不放心，可以自行查看源代码。
至于怎么开，诸位自己找个AI问一下吧。

项目中还自带了 `yad.plist.example` 文件，用于开机启动。需要根据自己的实际情况做修改。

成功运行后，就可以通过按下听写键说话。说完之后，松开听写键即可上屏。

好了，就先说这么多吧。这个项目主要是给我一个人用，没指望有多少人会用它，就不啰嗦了。

This is a small utility that uses better local ASR models, such as Qwen3 ASR, to replace macOS’s built-in dictation.

I really can’t be bothered to write a README. Just look at the sample config file `config.toml.example`, and you’ll probably figure out how to use it.

Note that this script requires Input Monitoring permission to run. If you launch it from the command line, you’ll need to enable Input Monitoring, Device Control, and Data Access permissions for your terminal or the TTY tool you normally use. These permissions are only used to monitor whether you’ve pressed the dictation key. If you’re not comfortable with that, feel free to inspect the source code yourself. As for how to enable them, ask an AI.

The project also includes a `yad.plist.example` file for launching at startup. You’ll need to modify it according to your own setup.

Once it’s running successfully, press the dictation key and speak. When you’re done, release the dictation key and the text will be entered into the active app.

OK, that’s all for now. This project is mainly for my own use, and I don’t expect many people to use it, so I’ll stop rambling.

:)
