脚本用于杀掉 MySQL 上的异常线程，如慢查询、被锁、处于Sleep状态的。

写这个脚本的初衷是在使用阿里云RDS的过程中，数据库出现异常，需要快速恢复。网上有许多类似的kill脚本，都是通过 mysqladmin 实现的。然后 Ali-RDS 环境有以下限制：
- 不提供 SUPER 权限的用户，也就是用户只能 kill 自己的线程
- 当连接数暴增时，外部用户无法登陆，包括控制台

为了解决上午2大问题，该 python 脚本通过在db实例上，使用多线程的方式，为每个用户保留一个连接，并**实时**读取指令配置文件 `mykill.ini`，发现有 kill 需求时，利用对应用户已有连接找到 `information_schema.processlist` 中符合条件的线程，并 kill 。

# 特性
1. 始终通过 mysql ping 维持一个长连接，并有断开自动重来机制，解决没有连接可用的尴尬局面
2. 每个用户有自己的线程，避免需要单独登陆个别用户去kill的繁复操作。
如果你具有 SUPER 权限，也可以简化配置做到兼容
3. 能够分开应对需要杀死线程的场景：
  - 长时间运行超过 N 秒的
  - 锁定的事务
  - Sleep 状态的事务 （一般不建议，但有时候kill它，可以快速释放连接给管理员使用）
  - 排除一些线程不能kill，如 Binlog dump （目前写死在脚本里）

# 使用方法
程序需要在后台保持运行，需要安装`MySQL-python`库，只在python 2.7上有测试。

是否真正 kill 线程设置了2个开关：
1. `kill_max_count`: 全局设置是否开启kill。如果为0，会禁用所有kill，但依然继续维护连接存活；如果为999，表示会在后台一直kill满足条件的线程，比如超过10s和locked thread 。还可以是常用值1，表示kill一次
2. `k_user`：需要kill 数据库哪个用户的连接。初始为 none ，表示不kill
为具体的用户名时，会根据名字去 db_info 节读取相应的密码



每次改动 kill_max_count，就会重新读取配置，即一个 clean start。所以改动其它配置项之后，同时需要更改这个值来生效。
如果有新加入db，则需要重新启动脚步。
目前假设的是不同db的端口和用户账号信息是相同的（即在我的环境里），只是数据库连接地址的差异。

**建议**
程序初始化启动的时候设置`mykill.ini`：
- `kill_max_count=0`
- `k_user=user1`
- `k_longtime=10`
- `k_lock=1`
- `k_sleep=0`

一般我们都会清楚是哪个用户连接异常比较多，提前设置好，需要用到的时候，直接修改`kill_max_count=1`，同时查看当前目录下的日志文件记录的操作。完后，归0

# 可配置项
killquery.ini :
```
[global]
; how many kill times once this config file changed
; 0: DISABLE all kill
; 999: always kill threads that meet kill conditions
; default: 1
kill_max_count=1

[db_info]
db_port=3306

DBid1_host=1.1.1.1
DBid2_host=1.1.1.2
DBid3_host=1.1.1.3

db_pass_user1=user1_passwd

db_pass_user2=user2_passwd

[DBid1]
; k_user: who's threads to be killed. use comma to separate
;         none: do not kill anyone's threads
;         all: kill all user's threads (with other where conditions)
; default: none
k_user=user1

; k_longtime: filter the threads who's running time is longer than this
;             0: ignore the time > x  condition
; default: 10
k_longtime=10

; k_lock: whether kill locked threads or not
;         0: do not kill state='Locked' threads from processlist
; default: 1
k_lock=1

; k_sleep: whether kill sleepd threads or not
;          0: do not kill command='Sleep' threads from processlist
;          when it set to 1, usually it's subset of k_longtime condition
; default: 0
k_sleep=0

[DBid2]
k_user=user1,user2
k_longtime=10
k_lock=1
k_sleep=0

[DBid3]
k_user=none
k_longtime=10
k_lock=1
k_sleep=0
```

**myquerykill.py** :
- `logger.setLevel(logging.INFO)` 可配置日志输出级别，`DEBUG`、`WARNING`等
- `CHECK_CONFIG_INTERVAL = 5` 检查文件改动的间隔时间
- `CHECK_PING_MULTI = 10` 保持与 MySQL Server 存活 ping 的时间（CHECK_CONFIG_INTERVAL * CHECK_PING_MULTI），主要考虑如果与 CHECK_CONFIG_INTERVAL 一样会太频繁，不超过`wait_timeout`就行


# 注意
配置文件中有许多数据库用户的密码信息，请确保它的安全。后续有空会把它加密
