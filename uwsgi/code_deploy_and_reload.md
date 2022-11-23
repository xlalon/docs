# uWSGI Graceful Deploy

---


### 重载，优雅重载

---


#### 暴力重载
```
Brutally killing worker 2 (pid: 17245)...
Brutally killing worker 1 (pid: 17244)...
goodbye to uWSGI.
...
spawned uWSGI worker 1 (pid: 9446, cores: 100)
spawned uWSGI worker 2 (pid: 9450, cores: 100)
...
```

问题:

    1. 如果你把重载当成“停止实例，启动实例”，那么这两个阶段之间的时间片将给你的客户带来粗鲁的无服务。
    2. 强行断开正在执行的请求潜在破坏数据完整性。

#### 优雅重载 ???
```
Gracefully killing worker 2 (pid: 83388)...
dealing with ongoing request...
Gracefully killing worker 1 (pid: 83387)...
goodbye to uWSGI.
...
spawned uWSGI worker 1 (pid: 9446, cores: 100)
spawned uWSGI worker 2 (pid: 9450, cores: 100)
...
```

解决问题： 2.

遗留问题： 1.


## uWSGI 重载

---


### 工作原理与理论背景

---

#### Pre-fork vs Lazy-app

![GitHub](./images/pre-fork.png)

---

#### Emperor mode

![GitHub](./images/emperor-mode.png)

---


### Signals for controlling uWSGI

|  Signal   | Description  | Convenience command|
|  ----  | ----  | ----- |
| SIGHUP  | gracefully reload all the workers and the master process | --reload
| SIGTERM  | brutally reload all the workers and the master process | (use --die-on-term to respect the convention of shutting down the instance)
| SIGINT  | immediately kill the entire uWSGI stack | --stop
| SIGQUIT  | immediately kill the entire uWSGI stack | 
| SIGUSR1  | print statistics |
| SIGUSR2  | print worker status or wakeup the spooler | 
| SIGURG  | restore a snapshot |
| SIGTSTP  | pause/suspend/resume an instance | 
| SIGWINCH  | wakeup a worker blocked in a syscall (internal use) | 
| SIGFPE  | generate C traceback | 
| SIGSEGV  | generate C traceback | 


#### The Master FIFO (uWSGI)
Generally you use UNIX signals to manage the master, but we are running out of signal numbers and (more importantly) 
not needing to mess with PIDs greatly simplifies the implementation of external management scripts.

So, instead of signals, you can tell the master to create a UNIX named pipe (FIFO) that you may use to issue commands to the master.


To create a FIFO just add --master-fifo <filename> then start issuing commands to it.
```
echo r > /tmp/yourfifo
```


#### Available commands
```
‘0’ to ‘9’ - set the fifo slot (see below)
‘+’ - increase the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
‘-’ - decrease the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
‘B’ - ask Emperor for reinforcement (broodlord mode, requires uWSGI >= 2.0.7)
‘C’ - set cheap mode
‘c’ - trigger chain reload
‘E’ - trigger an Emperor rescan
‘f’ - re-fork the master (dangerous, but very powerful)
‘l’ - reopen log file (need –log-master and –logto/–logto2)
‘L’ - trigger log rotation (need –log-master and –logto/–logto2)
‘p’ - pause/resume the instance
‘P’ - update pidfiles (can be useful after master re-fork)
‘Q’ - brutally shutdown the instance
‘q’ - gracefully shutdown the instance
‘R’ - send brutal reload
‘r’ - send graceful reload
‘S’ - block/unblock subscriptions
‘s’ - print stats in the logs
‘W’ - brutally reload workers
‘w’ - gracefully reload workers
```


### 重载方式

---

#### re-exec master ("r")

![GitHub](./images/reload-r.png)

---

#### restart workers ("w")

![GitHub](./images/reload-w.png)

---

#### chain restart workers ("c")

![GitHub](./images/reload-c.png)

---

#### fork master ("f")

![GitHub](./images/reload-f.png)

---

#### Zerg dance

![GitHub](./images/zerg-dance.png)

---


### 选择方式

---

## 进程管理工具

### Supervisor

优点：

缺点：

### Systemd

优点：

缺点：

### Upstart

优点：

缺点：


## 参考文档

