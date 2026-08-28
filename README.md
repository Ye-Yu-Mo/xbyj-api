# xbyj

小倍养基命令行工具。

## 安装

```bash
pip install -e .
```

## 使用

```bash
# 登录（手机号 + 验证码）
xbyj login

# 查询基金估值（支持多个代码）
xbyj estimate 000001 110022

# 查看持仓
xbyj holdings

# 查询历史净值
xbyj nav 000001
xbyj nav 000001 --start 2025-01-01 --end 2025-03-01

# 查看大盘概览和主要指数
xbyj market

# 查看热门板块 / 板块涨幅榜
xbyj sector-hot
xbyj sector-rank

# 查看某个板块的热门基金
xbyj sector-funds XB1094

# 查看基金估值涨幅/跌幅榜、连涨/连跌榜
xbyj rank --type quote --direction up
xbyj rank --type streak --direction down

# 查看基金快讯
xbyj news

# 查看自选列表
xbyj pick

# 查看基金重仓股
xbyj position 025209

# 查看基金基本信息
xbyj fund 025209

# 查看账户列表和用户信息
xbyj account

# 查询行业/指数估值
xbyj industry-yield 886033.TI 000016.SH

# 查看会员权益
xbyj benefits

# 查看未读消息
xbyj messages

# 查看基金机会信号（波段/趋势/反转/回撤抄底）
xbyj opportunity --kind swing
xbyj opportunity --kind trend

# 登出
xbyj logout
```

## 命令一览

| 命令 | 说明 | 示例 |
| --- | --- | --- |
| `login` | 手机号 + 验证码登录 | `xbyj login` |
| `logout` | 清除本地登录态 | `xbyj logout` |
| `estimate` | 查询基金估值 | `xbyj estimate 000001 110022` |
| `holdings` | 查看当前持仓 | `xbyj holdings` |
| `nav` | 查询历史净值 | `xbyj nav 000001 --start 2025-01-01` |
| `market` | 查看大盘概览和主要指数 | `xbyj market` |
| `sector-hot` | 查看热门板块 | `xbyj sector-hot --limit 10` |
| `sector-rank` | 查看板块涨幅榜 | `xbyj sector-rank --limit 10` |
| `sector-funds` | 查看板块热门基金 | `xbyj sector-funds XB1094` |
| `rank` | 基金涨幅/跌幅榜、连涨/连跌榜 | `xbyj rank --type quote --direction up` |
| `news` | 查看基金快讯 | `xbyj news --page 1 --limit 10` |
| `pick` | 查看自选列表估值 | `xbyj pick` |
| `position` | 查看基金重仓股 | `xbyj position 025209` |
| `fund` | 查看基金基本信息 | `xbyj fund 025209` |
| `account` | 查看账户列表和用户信息 | `xbyj account` |
| `industry-yield` | 查询行业/指数估值 | `xbyj industry-yield 886033.TI 000016.SH` |
| `benefits` | 查看会员权益 | `xbyj benefits` |
| `messages` | 查看未读消息 | `xbyj messages` |
| `opportunity` | 查看基金机会信号 | `xbyj opportunity --kind swing` |

## Token 存储

登录后 token 保存在 `~/.xbyj/config.json`，无需每次重新登录。

## API 文档

接口文档见 [API.md](API.md)。
