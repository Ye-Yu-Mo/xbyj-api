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

# 登出
xbyj logout
```

## Token 存储

登录后 token 保存在 `~/.xbyj/config.json`，无需每次重新登录。
