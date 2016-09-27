脚本用于杀掉 MySQL 上的异常线程，如慢查询、处于Sleep状态的。

写这个脚本的初衷是在使用阿里云RDS的过程中，数据库出现异常，需要快速恢复。网上有许多类似的kill脚本，都是通过 mysqladmin 实现的。然而 Ali-RDS 环境有以下限制：
- 不提供 SUPER 权限的用户，也就是用户只能 kill 自己的线程
- 当连接数暴增时，外部用户无法登陆，包括控制台

为了解决上午2大问题，该 python 脚本通过在db实例上，使用多线程的方式，为每个用户保留一个连接，并**实时**读取指令配置文件 `mysqk.ini`，发现有 kill 需求时，利用对应用户已有连接找到 `information_schema.processlist` 中符合条件的线程，并 kill 。

说明：该脚本在9月份做过一次重写，7月份的版本（分支 old_0.5.0）是每实例每用户，对应一个线程，db实例一多线程数也太多，看得始终不太优雅，于是改成了一个db实例一个线程，维护同时维护多个用户的会话。同时新版也加入了更多的功能，如按时间窗口检查，包含或排除特定连接，邮件通知，配置项覆盖。

# 特性
1. 始终通过 mysql ping 维持一个长连接，并有断开自动重来机制，解决没有连接可用的尴尬局面
2. 每个db实例有自己的线程，避免需要单独登陆个别用户去kill的繁复操作。
如果你具有 SUPER 权限，也可以简化配置做到兼容
3. 能够分开应对需要杀死线程的场景：
  - 长时间运行超过 N 秒的
  - Sleep 状态的事务 （一般不建议，但有时候kill它，可以快速释放连接给管理员使用）
  - 排除一些线程不能kill，如 Binlog dump
  - 包含特定关键字的线程要kill
4. 出现符合条件的线程时，会对当时的processlist, engine status，lock_wait 做一个快照，并邮件发出
5. 有试运行dry_run模式，即执行所有的检查过程但不真正kill
6. 支持只在时间窗口内运行，考虑到晚上一些长任务不检查
7. 密码加密

# 快速使用
需要pip安装`MySQL-python`和`pycrypto`两个库，只在python 2.7上有测试。

在 *settings.py* 里面设置连接的用户名和密码信息。这里假设同一批db的要check的认证信息是一样的，指定的用户既用于登录认证，也用于告知脚本哪些用户需要被检查。
密码要通过 `prpcryptec.py` 加密，加密的密钥需写入脚本本身的 `KEY_DB_AUTH`变量。（担心泄露的话，把mysqk.py编译成 pyc 来跑）

在 *mysqk.ini* 主配置文件里面  
 - `db_info` 节设置需要被检查的数据库地址，如 `db01=10.0.200.100:3306`
 - 可分别 `db01`等指定需要kill thread的选项。`[id_db01]` 则默认复用 `[db_commkill]` 的选项
 - `db_comconfig` 节设置 `db_puser` 为能查看到所有processlist的权限用户，且在 *settings.py* 的DB_AUTH中已指定
 - 只想执行检查，并不想真正kill异常线程，确认 dry_run不等于0

 Here we go!

# 配置项说明

**`mysqk.ini`**：

## mail_config
邮件通知相关设置，smtp服务地址和认证信息。
`mail_receiver=` 设置空，表示不发邮件

## db_info
设置要检查kill哪些数据库实例.
格式：`<dbid>=<host>:<port>`，dbid是唯一表示db实例的，后面设置各db需要被kill的选项，小节配置名就是 `id_<dbid>`；端口必需指定。

在这里出现的db实例都会被执行检查，可用 ; 注释，但需要重启脚本。

## db_comconfig
检查用公共配置，实时生效。

- `db_puser`：指定一个用户名用于 show processlist，需要的权限：PROCESS、information_schema库查看。可以认为是一个代表用户，检查异常thread，把结果提供给有该thread杀掉权限用户。
- `run_max_count`：执行检查的次数，是一个全局控制开关。每次修改这个值都会重新开始检查，即一个 clean start，让刚修改的配置生效。
  - 为 0 表示脚本不进行任何检查，只简单维护与数据库的连接存活。存活检查频率在 *settings.py* 由 `CHECK_CONFIG_INTERVAL × CHECK_PING_MULTI`决定
  - 为 999 表示会在后台一致检查连接线程（但不一定有符合kill条件的），检查的频率在 *settings.py* 里面 `CHECK_CONFIG_INTERVAL` 指定
  - 为其它值时，表示检查次数满后停止检查
- `dry_run`：是否开启试运行模式，为0表示真实kill，为1或其它值表示试运行。试运行模式可用于监控慢查询并告警。注意同一会话线程ID只告警一次
- `run_time_window`：运行的检查的时间窗口，格式如 `08:00-22:00`，在这个时间以外不执行检查，留空表示不限制。主要考虑晚上一些统计任务可能出现“异常”线程。

## db_commkill
kill用公共配置，实时生效，会被 `id_<dbid>` 节的选项覆盖。

- `k_user`：很关键的一个选项，表示你要检查并kill哪些数据库用户，多个用逗号分隔（不要带引号）。  
  为 `all` 时，表示要检查 *settings.py* 里 DB_AUTH 指定的所有用户  
  为 `none` 时，表示不kill任何异常线程，效果与设置了 dry_run 模式相当  

- `k_longtime`：执行超过设定值的sql则认为异常。一般大于 CHECK_CONFIG_INTERVAL
- `k_sleep`：Sleep超过设定秒的sql则认为异常，为 0 表示不杀掉sleep状态的线程
- `k_exclude`：排除掉那些特定关键字的线程，比如复制线程、管理员的连接等
- `k_include`：包含这些特定关键字的线程，需要被kill。注意，它作用在满足 k_user 和 k_exclude 的前提之下。  
  k_exclude与k_include 的值是支持python re模块正则的格式，不要带引号

## id_<dbid>
这部分区域的配置项与 db_commconfig 相同，用于针对个别db的kill选项。

# 使用建议

两种组合模式：

1. 设置 `dry_run=0`，默认 `k_user=none`，当数据库出现异常时，主动修改对应db的k_user值，动态kill
2. 设置 `dry_run=1`，默认 `k_user=all`，相当于运行在daemon模式，有慢查询则邮件通知，并且记录下当时的信息

当然你也可以`dry_run=0`，`k_user=all`，让程序一直在后台跑并kill，但生产环境极不推荐。

有日志和快照文件可以查看。


# 配置文件示例
mysqlk.ini :

```
[mail_config]
mail_host=smtp.exmail.qq.com
mail_user=xxx@ecqun.com
mail_pass=xxxxxx

mail_receiver=

[db_info]
crm0=192.168.1.125:3306
crm1=192.168.1.126:3306
crm2=192.168.1.127:3306
crm3=192.168.1.128:3306
base=10.0.200.142:3306

[db_commconfig]
db_puser=ecuser

; how many kill times once this config file changed
; 0: DISABLE all kill
; 999: always kill threads that meet kill conditions
; default: 1
; can not be inherit
run_max_count=999
dry_run=1
run_time_window=08:00-22:00


[db_commkill]
k_user=all
k_longtime=10
k_lock=1
k_sleep=0

k_exclude=Binlog|ecdba|Daemon
k_include=select sleep\(17\)


[id_crm0]
; k_user: who's threads to be killed. use comma to separate
;         none: do not kill anyone's threads
;         all: kill all user's threads (with other where conditions)
; default: none
k_user=all

; k_longtime: filter the threads who's running time is longer than this
;             0: ignore the time > x  condition
; default: 10
k_longtime=10

; k_sleep: whether kill sleepd threads or not
;          0: do not kill command='Sleep' threads from processlist
;          when it set to 1, usually it's subset of k_longtime condition
; default: 0
k_sleep=0

[id_crm1]
k_user=ecuser
k_longtime=10
k_sleep=0

[id_crm2]
k_user=all
k_longtime=10
k_sleep=0

[id_crm3]
```
