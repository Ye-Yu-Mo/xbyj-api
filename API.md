# xbyj API 文档

## 基本信息

| 项目 | 值 |
| --- | --- |
| 旧版 API Host | `https://api.xiaobeiyangji.com` |
| 新版 API Host | `https://apiv2.xiaobeiyangji.com` |
| 当前接口版本号 | `3.8.9.0` |
| 认证方式 | `Authorization: Bearer <accessToken>` |
| 请求方式 | 均为 `POST`，`Content-Type: application/json` |

所有需要登录的接口都会携带以下公共字段：

```json
{
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

登录接口使用 `clientType: "PHONE"`。

## 响应格式

旧版 API 响应：

```json
{
  "code": 200,
  "msg": "请求成功",
  "data": {}
}
```

新版 apiv2 响应：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {}
}
```

`code` 为 `200` 时表示成功，否则可读取 `msg` / `message` 获取错误信息。

---

## 登录 / 账号

### 1. 发送短信验证码

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/send-sms`

请求体：

```json
{
  "phoneNumber": "your_phone_number",
  "isBind": false,
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data` 为提示文本。

### 2. 手机号验证码登录

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/login/phone`

请求体：

```json
{
  "phone": "your_phone_number",
  "code": "957061",
  "clientType": "PHONE",
  "version": "3.8.9.0"
}
```

响应 `data` 主要字段：

```json
{
  "accessToken": "...",
  "refreshToken": "...",
  "expiresIn": 2592000,
  "user": {
    "uid": "17104647",
    "phone": "your_phone_number",
    "nickName": "youe_nickname",
    "unionId": "your_phone_number"
  }
}
```

### 3. 获取账户列表和用户信息

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-account-list`

请求体：

```json
{
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data` 主要字段：

```json
{
  "accountList": [
    {
      "name": "默认账户",
      "accountId": 0,
      "createTime": "...",
      "updateTime": "..."
    }
  ],
  "userInfo": {
    "uid": "17104647",
    "nickName": "...",
    "unionId": "..."
  }
}
```

CLI：`xbyj account`

---

## 基金

### 4. 基金详情

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-fund-detail-v310`

请求体：

```json
{
  "code": "025209",
  "accountId": "",
  "dataResources": "4",
  "dataSourceSwitch": true,
  "isHasPosition": true,
  "fromType": "home",
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data` 主要字段：

```json
{
  "code": "025209",
  "name": "永赢先锋半导体智选混合发起式C",
  "investType": "混合型",
  "nav": 2.4036,
  "dailyYield": -0.02061771656751699,
  "setupDate": "2025-09-12",
  "latestPriceDate": "2026-08-28",
  "hasValuationSource": true
}
```

CLI：`xbyj fund 025209`

### 5. 实时估值序列

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-net-worth-es`

请求体：

```json
{
  "code": "025209",
  "dataResources": "2",
  "dataSourceSwitch": true,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data` 为估值时间序列数组，最后一条通常为最新估值/净值：

```json
[
  {
    "date": "2026-08-28",
    "update": "09:15:27",
    "quote": 2.4755,
    "change": 0.0087,
    "source": "syncComputeStockQuote"
  }
]
```

CLI：`xbyj estimate 025209` 在非自选基金时会回退到该接口。

### 6. 历史净值

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-trajectory-v310`

请求体：

```json
{
  "code": "025209",
  "type": "normal",
  "range": 3,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.data` 为净值序列：

```json
{
  "data": [
    {
      "d": "2026-05-27",
      "n": 2.4149,
      "y": 0.009489173146058016
    }
  ]
}
```

CLI：`xbyj nav 000001 --start 2025-01-01 --end 2025-03-01`

### 7. 基金重仓股

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-fund-position-ratio`

请求体：

```json
{
  "code": "025209",
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.data[0]` 为当前基金持仓明细，主要字段：

```json
{
  "fundCode": "025209",
  "reportDate": "2026-06-30",
  "position": [
    {
      "code": "603986",
      "name": "兆易创新",
      "weight": 7.92,
      "change": -0.034970817120622555,
      "industry": "半导体"
    }
  ],
  "lastPosition": [
    {
      "stock_code": "001309",
      "stock_name": "德明利",
      "weight": 9.51
    }
  ]
}
```

CLI：`xbyj position 025209`

---

## 自选 / 持仓

### 8. 自选列表估值

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/user/pickList/getList`

请求体：

```json
{
  "page": 0,
  "groupId": "",
  "dataResources": "2",
  "dataSourceSwitch": true,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.list` 主要字段：

```json
{
  "list": [
    {
      "code": "025209",
      "name": "永赢先锋半导体智选混合发起式C",
      "nav": 2.4036,
      "navY": -0.02061771656751699,
      "valuation": 2.4036,
      "valuationY": -0.02061771656751699,
      "snapshotValuation": 2.4036,
      "snapshotValuationY": -0.02061771656751699
    }
  ],
  "total": 3,
  "page": 0,
  "pageSize": 3,
  "valuationDate": "2026-08-28",
  "navDate": "2026-08-28"
}
```

CLI：`xbyj pick`

### 9. 持仓列表

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/user/get-hold-list`

请求体：

```json
{
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.list` 主要字段：

```json
{
  "list": [
    {
      "code": "025209",
      "name": "永赢先锋半导体智选混合发起式C",
      "money": 17926.801594973404,
      "earnings": 5603.80159497342,
      "nav": 2.4036,
      "navY": -0.02061771656751699,
      "holdLot": 7458.31319478009
    }
  ]
}
```

CLI：`xbyj holdings`

---

## 行情 / 资讯

### 10. 大盘概览

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-market-overview`

请求体：

```json
{
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data`：

```json
{
  "northbound": 0,
  "market": -34371004473,
  "emotion": -0.6165132783297986
}
```

CLI：`xbyj market`

### 11. 主要指数列表

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-market-index-list`

请求体：

```json
{
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data` 为指数数组：

```json
[
  {
    "code": "000001.SH",
    "name": "上证指数",
    "current": 3952.18,
    "chg": -4.39,
    "percent": -0.11
  }
]
```

CLI：`xbyj market`

### 12. 基金快讯

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/flash-news/list`

请求体：

```json
{
  "page": 1,
  "pageSize": 10,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.list`：

```json
{
  "list": [
    {
      "_id": "...",
      "title": "标题",
      "content": "正文",
      "publishTime": "2026-08-28T12:29:22.000Z",
      "red": false,
      "sectors": []
    }
  ]
}
```

CLI：`xbyj news --page 1 --limit 10`

### 13. 行业/指数估值

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-industry-optional-yield-price-v350`

请求体：

```json
{
  "dataResources": "2",
  "dataSourceSwitch": true,
  "valuationDate": "2026-08-28",
  "navDate": "2026-08-28",
  "isTD": true,
  "codeArr": ["886033.TI", "000016.SH"],
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data`：

```json
[
  {
    "code": "886033.TI",
    "yield": -0.0114248858645321,
    "open": 5897.81,
    "close": 5841.261,
    "isUpdate": false,
    "isUpdateShow": false
  }
]
```

CLI：`xbyj industry-yield 886033.TI 000016.SH`

---

## 板块

### 14. 热门板块

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/valuation/sectorHeatTop`

请求体：

```json
{
  "limit": 10,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.list`：

```json
{
  "list": [
    {
      "sectorCode": "XB1038",
      "extraCode": "886033.TI",
      "sectorName": "CPO",
      "changeRate": -0.0114248858645321,
      "heat": 2125591.0
    }
  ]
}
```

CLI：`xbyj sector-hot --limit 10`

### 15. 板块涨幅榜

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/valuation/sectorQuoteRank`

请求体：

```json
{
  "limit": 10,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.list`：

```json
{
  "list": [
    {
      "sectorCode": "XB1085",
      "extraCode": "000813.CSI",
      "sectorName": "化工",
      "changeRate": 0.02027859001259264,
      "streakState": {
        "type": "up",
        "days": 3
      }
    }
  ]
}
```

CLI：`xbyj sector-rank --limit 10`

### 16. 板块热门基金

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/valuation/sectorFundHeatTop/getBySectorCode`

请求体：

```json
{
  "sectorCode": "XB1094",
  "limit": 10,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.list`：

```json
{
  "list": [
    {
      "fundCode": "003096",
      "fundName": "中欧医疗健康混合C",
      "extraCode": "875217.TI",
      "changeRate": -0.0148804812,
      "heat": 1766503
    }
  ]
}
```

CLI：`xbyj sector-funds XB1094`

---

## 榜单

### 17. 基金估值涨幅/跌幅榜

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/valuation/fundQuoteRank/findTopQuoteRank`

请求体：

```json
{
  "fundType": "all",
  "limit": 20,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.upList` / `data.downList`：

```json
{
  "upList": [
    {
      "fundCode": "027300",
      "fundName": "富国电子信息产业混合发起式C",
      "changeRate": "0.050333792518808984",
      "sectorCode": "931573.CSI",
      "sectorName": "港股科技",
      "sectorChangeRate": -0.0025257037243283137
    }
  ],
  "downList": []
}
```

CLI：`xbyj rank --type quote --direction up`

### 18. 基金连涨/连跌榜

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/valuation/fundStreakState/findTopStreakRanking`

请求体：

```json
{
  "fundType": "all",
  "limit": 20,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.upList` / `data.downList`：

```json
{
  "upList": [
    {
      "fundCode": "010502",
      "fundName": "财通裕泰87个月定开债",
      "streakDays": 433,
      "firstClass": "债券型",
      "sectorCode": "511090.SH",
      "sectorName": "长债",
      "sectorChangeRate": -0.00005915259679892166
    }
  ],
  "downList": []
}
```

CLI：`xbyj rank --type streak --direction up`

---

## 会员 / 消息 / 机会

### 19. 会员权益

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/memberBenefit/list`

请求体：

```json
{
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data` 为权益数组：

```json
[
  {
    "code": "SIGNALS",
    "name": "波段信号",
    "description": "把握基金高低位，高抛低吸",
    "promoTag": "小倍年度热卖",
    "tag": ""
  }
]
```

CLI：`xbyj benefits`

### 20. 未读互动消息

- Host: `apiv2.xiaobeiyangji.com`
- Path: `POST /api/app/user/get-message`

请求体：

```json
{
  "isList": false,
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data`：

```json
[
  {
    "_id": "comment",
    "count": 0
  },
  {
    "_id": "like",
    "count": 0
  },
  {
    "_id": "cue",
    "count": 0
  }
]
```

CLI：`xbyj messages`

### 21. 系统消息未读数

- Host: `api.xiaobeiyangji.com`
- Path: `POST /yangji-api/api/get-user-system-news`

请求体：

```json
{
  "isList": false,
  "type": "public",
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data` 为数字未读数。

CLI：`xbyj messages`

### 22. 基金机会信号

- Host: `apiv2.xiaobeiyangji.com`
- Path: 以下四个接口之一：
  - `POST /api/app/user/valuation/fundSwingSignalsOpportunityByPage`
  - `POST /api/app/user/valuation/fundTrendStrengthOpportunityByPage`
  - `POST /api/app/user/valuation/fundAmazingReversalOpportunityByPage`
  - `POST /api/app/user/valuation/fundBuyOnDipsOpportunityByPage`

请求体示例（`swing`）：

```json
{
  "zone": "highZone",
  "page": 1,
  "holdAndPick": true,
  "template": "default",
  "unionId": "your_phone_number",
  "version": "3.8.9.0",
  "clientType": "APP"
}
```

响应 `data.list`：

```json
{
  "total": 0,
  "page": 1,
  "pageSize": 20,
  "list": []
}
```

CLI：`xbyj opportunity --kind swing`

---
