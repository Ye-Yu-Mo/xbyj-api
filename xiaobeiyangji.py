"""
小倍养基 CLI 工具
"""
import json
import logging
import math
import requests
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

logger = logging.getLogger(__name__)
console = Console()

# ─── Config ───────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / '.xbyj' / 'config.json'


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def save_config(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


# ─── Source ───────────────────────────────────────────────────────────────────

class XiaoBeiYangJiSource:
    """小倍养基数据源（手机号登录）"""

    BASE_URL = 'https://api.xiaobeiyangji.com'
    APIV2_BASE_URL = 'https://apiv2.xiaobeiyangji.com'
    VERSION = '3.8.9.0'

    def __init__(self):
        self._token = None
        self._union_id = None
        self._pick_valuations = None

    def set_token(self, token: str):
        """设置 token 并自动从 JWT payload 提取 union_id"""
        import base64
        self._token = token
        try:
            payload = token.split('.')[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = json.loads(base64.b64decode(payload))
            self._union_id = decoded.get('unionId')
        except Exception:
            logger.warning('无法从 token 解析 unionId')

    def _common_body(self) -> Dict:
        return {
            'unionId': self._union_id,
            'version': self.VERSION,
            'clientType': 'APP',
        }

    def _request(self, method: str, path: str, base_url: str = None, **kwargs) -> Dict:
        if base_url is None:
            base_url = self.BASE_URL
        url = base_url + path
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._token or ""}',
        }
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 200:
            msg = result.get('msg') or result.get('message') or 'Unknown error'
            raise Exception(f"API 错误: {msg}")
        return result.get('data')

    def _request_v2(self, method: str, path: str, **kwargs) -> Dict:
        return self._request(method, path, base_url=self.APIV2_BASE_URL, **kwargs)

    # ─── 登录 ────────────────────────────────────────────────────────────────

    def send_sms(self, phone: str) -> None:
        """发送短信验证码"""
        url = self.BASE_URL + '/yangji-api/api/send-sms'
        body = {
            'phoneNumber': phone,
            'isBind': False,
            'version': self.VERSION,
            'clientType': 'APP',
        }
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '},
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 200:
            raise Exception(f"发送短信失败: {result.get('msg', 'Unknown error')}")

    def verify_phone(self, phone: str, code: str) -> dict:
        """手机号 + 验证码登录，返回 token 和 union_id"""
        url = self.BASE_URL + '/yangji-api/api/login/phone'
        body = {
            'phone': phone,
            'code': code,
            'clientType': 'PHONE',
            'version': self.VERSION,
        }
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '},
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 200:
            raise Exception(f"登录失败: {result.get('msg', 'Unknown error')}")
        data = result['data']
        self._token = data['accessToken']
        self._union_id = data['user']['unionId']
        return {'token': self._token, 'union_id': self._union_id}

    # ─── 估值 ────────────────────────────────────────────────────────────────

    def _get_pick_valuations(self) -> Dict[str, Dict]:
        """获取自选列表的估值快照（新 API 替代 get-optional-change-nav）"""
        if self._pick_valuations is None:
            body = {
                'page': 0,
                'groupId': '',
                'dataResources': '2',
                'dataSourceSwitch': True,
                **self._common_body(),
            }
            data = self._request_v2(
                'POST',
                '/api/app/user/pickList/getList',
                json=body,
            )
            items = data.get('list', []) if data else []
            self._pick_valuations = {x['code']: x for x in items}
        return self._pick_valuations

    def _get_net_worth_es(self, fund_code: str) -> List[Dict]:
        """获取单支基金的实时估值序列"""
        body = {
            'code': fund_code,
            'dataResources': '2',
            'dataSourceSwitch': True,
            **self._common_body(),
        }
        return self._request('POST', '/yangji-api/api/get-net-worth-es', json=body)

    def _get_fund_detail(self, fund_code: str) -> Dict:
        """获取基金详情（含名称）"""
        body = {
            'code': fund_code,
            'accountId': '',
            'dataResources': '4',
            'dataSourceSwitch': True,
            'isHasPosition': True,
            'fromType': 'home',
            **self._common_body(),
        }
        return self._request('POST', '/yangji-api/api/get-fund-detail-v310', json=body)

    def fetch_estimate(self, fund_code: str) -> Optional[Dict]:
        """获取单支基金估值"""
        pick_item = self._get_pick_valuations().get(fund_code)
        if pick_item:
            return {
                'fund_code': fund_code,
                'fund_name': pick_item.get('name', ''),
                'estimate_nav': Decimal(str(pick_item.get('valuation') or pick_item.get('nav') or 0)),
                'estimate_growth': Decimal(str(pick_item.get('valuationY') or pick_item.get('navY') or 0)) * 100,
                'estimate_time': datetime.now(),
            }

        series = self._get_net_worth_es(fund_code)
        if not series:
            detail = self._get_fund_detail(fund_code)
            if not detail:
                return None
            return {
                'fund_code': fund_code,
                'fund_name': detail.get('name', ''),
                'estimate_nav': Decimal(str(detail.get('nav') or 0)),
                'estimate_growth': Decimal(str(detail.get('dailyYield') or 0)) * 100,
                'estimate_time': datetime.now(),
            }
        item = series[-1]

        estimate_nav = Decimal(str(item.get('quote') or 0))
        estimate_growth = Decimal(str(item.get('change') or 0)) * 100

        # 优先使用服务端返回的估值时间，解析失败再用本地时间兜底
        estimate_time = datetime.now()
        try:
            estimate_time = datetime.strptime(
                f"{item.get('date', '')} {item.get('update', '')}",
                '%Y-%m-%d %H:%M:%S',
            )
        except (TypeError, ValueError):
            pass

        detail = self._get_fund_detail(fund_code)
        fund_name = detail.get('name', '') if detail else ''

        return {
            'fund_code': fund_code,
            'fund_name': fund_name,
            'estimate_nav': estimate_nav,
            'estimate_time': estimate_time,
            'estimate_growth': estimate_growth,
        }

    def fetch_holdings(self) -> List[Dict]:
        """获取持仓列表"""
        data = self._request_v2(
            'POST',
            '/api/app/user/get-hold-list',
            json=self._common_body(),
        )
        items = data.get('list', []) if data else []
        valid_items = [x for x in items if x.get('money')]
        if not valid_items:
            return []

        result = []
        for item in valid_items:
            fund_code = item['code']
            money = Decimal(str(item['money']))
            earnings = Decimal(str(item.get('earnings', 0)))
            nav = Decimal(str(item.get('nav', 0)))
            hold_lot = item.get('holdLot') or (money / nav if nav else 0)
            fund_name = (
                item.get('name')
                or (item.get('data') or {}).get('name')
                or ''
            )
            share = Decimal(str(hold_lot)).quantize(Decimal('0.01')) if hold_lot else Decimal('0')
            result.append({
                'fund_code': fund_code,
                'fund_name': fund_name,
                'share': share,
                'nav': nav,
                'amount': money,
                'earnings': earnings,
            })
        return result

    # ─── 行情 / 资讯 / 榜单 ─────────────────────────────────────────────────

    def fetch_market_overview(self) -> Dict:
        """获取大盘概览"""
        return self._request(
            'POST',
            '/yangji-api/api/get-market-overview',
            json=self._common_body(),
        ) or {}

    def fetch_market_indices(self) -> List[Dict]:
        """获取主要指数行情"""
        return self._request(
            'POST',
            '/yangji-api/api/get-market-index-list',
            json=self._common_body(),
        ) or []

    def fetch_flash_news(self, page: int = 1, page_size: int = 10) -> List[Dict]:
        """获取快讯列表"""
        body = {
            'page': page,
            'pageSize': page_size,
            **self._common_body(),
        }
        data = self._request(
            'POST',
            '/yangji-api/api/flash-news/list',
            json=body,
        )
        return (data or {}).get('list', [])

    def fetch_sector_heat(self, limit: int = 10) -> List[Dict]:
        """获取热门板块"""
        body = {'limit': limit, **self._common_body()}
        data = self._request_v2(
            'POST',
            '/api/app/valuation/sectorHeatTop',
            json=body,
        )
        return (data or {}).get('list', [])

    def fetch_sector_quote_rank(self, limit: int = 10) -> List[Dict]:
        """获取板块涨幅榜"""
        body = {'limit': limit, **self._common_body()}
        data = self._request_v2(
            'POST',
            '/api/app/valuation/sectorQuoteRank',
            json=body,
        )
        return (data or {}).get('list', [])

    def fetch_sector_fund_heat(self, sector_code: str, limit: int = 10) -> List[Dict]:
        """获取指定板块的热门基金"""
        body = {
            'sectorCode': sector_code,
            'limit': limit,
            **self._common_body(),
        }
        data = self._request_v2(
            'POST',
            '/api/app/valuation/sectorFundHeatTop/getBySectorCode',
            json=body,
        )
        return (data or {}).get('list', [])

    def fetch_fund_quote_rank(self, fund_type: str = 'all', limit: int = 20) -> Dict:
        """获取基金估值涨幅/跌幅榜"""
        body = {
            'fundType': fund_type,
            'limit': limit,
            **self._common_body(),
        }
        return self._request_v2(
            'POST',
            '/api/app/valuation/fundQuoteRank/findTopQuoteRank',
            json=body,
        ) or {}

    def fetch_fund_streak_rank(self, fund_type: str = 'all', limit: int = 20) -> Dict:
        """获取基金连涨/连跌榜"""
        body = {
            'fundType': fund_type,
            'limit': limit,
            **self._common_body(),
        }
        return self._request_v2(
            'POST',
            '/api/app/valuation/fundStreakState/findTopStreakRanking',
            json=body,
        ) or {}

    def fetch_pick_list(self) -> List[Dict]:
        """获取自选列表"""
        return list(self._get_pick_valuations().values())

    def fetch_fund_position_ratio(self, fund_code: str) -> Dict:
        """获取基金持仓/重仓股"""
        body = {
            'code': fund_code,
            **self._common_body(),
        }
        data = self._request(
            'POST',
            '/yangji-api/api/get-fund-position-ratio',
            json=body,
        ) or {}
        # 接口返回 data.data[0] 为当前基金的持仓明细
        items = data.get('data') or []
        if items:
            return items[0]
        return data

    def fetch_account_list(self) -> Dict:
        """获取账户列表和用户信息"""
        return self._request(
            'POST',
            '/yangji-api/api/get-account-list',
            json=self._common_body(),
        ) or {}

    def fetch_industry_optional_yield(self, codes: List[str]) -> List[Dict]:
        """批量获取行业/指数估值涨跌"""
        body = {
            'dataResources': '2',
            'dataSourceSwitch': True,
            'valuationDate': date.today().isoformat(),
            'navDate': date.today().isoformat(),
            'isTD': True,
            'codeArr': codes,
            **self._common_body(),
        }
        return self._request(
            'POST',
            '/yangji-api/api/get-industry-optional-yield-price-v350',
            json=body,
        ) or []

    def fetch_member_benefits(self) -> List[Dict]:
        """获取会员权益列表"""
        return self._request_v2(
            'POST',
            '/api/app/memberBenefit/list',
            json=self._common_body(),
        ) or []

    def fetch_message_counts(self) -> List[Dict]:
        """获取互动消息未读数"""
        body = {
            'isList': False,
            **self._common_body(),
        }
        return self._request_v2(
            'POST',
            '/api/app/user/get-message',
            json=body,
        ) or []

    def fetch_system_news_count(self) -> int:
        """获取系统消息未读数"""
        body = {
            'isList': False,
            'type': 'public',
            **self._common_body(),
        }
        return self._request(
            'POST',
            '/yangji-api/api/get-user-system-news',
            json=body,
        ) or 0

    def fetch_fund_opportunity(self, kind: str = 'swing', page: int = 1, hold_and_pick: bool = True) -> Dict:
        """获取基金机会信号列表"""
        path_map = {
            'swing': '/api/app/user/valuation/fundSwingSignalsOpportunityByPage',
            'trend': '/api/app/user/valuation/fundTrendStrengthOpportunityByPage',
            'reversal': '/api/app/user/valuation/fundAmazingReversalOpportunityByPage',
            'dips': '/api/app/user/valuation/fundBuyOnDipsOpportunityByPage',
        }
        if kind == 'swing':
            body = {
                'zone': 'highZone',
                'page': page,
                'holdAndPick': hold_and_pick,
                'template': 'default',
                **self._common_body(),
            }
        elif kind == 'trend':
            body = {
                'displayState': 'weakening',
                'page': page,
                'holdAndPick': hold_and_pick,
                'template': 'balanced',
                **self._common_body(),
            }
        elif kind == 'reversal':
            body = {
                'zone': 'upReversalZone',
                'page': page,
                'holdAndPick': hold_and_pick,
                **self._common_body(),
            }
        else:
            body = {
                'zone': 'highWinZone',
                'page': page,
                'holdAndPick': hold_and_pick,
                **self._common_body(),
            }
        return self._request_v2(
            'POST',
            path_map.get(kind, path_map['swing']),
            json=body,
        ) or {}

    def fetch_nav_history(
        self,
        fund_code: str,
        start_date: date = None,
        end_date: date = None,
    ) -> List[Dict]:
        """获取历史净值"""
        if start_date and end_date:
            months = math.ceil((end_date - start_date).days / 30)
            range_months = min(max(months, 1), 12)
        else:
            range_months = 3

        body = {
            'code': fund_code,
            'type': 'normal',
            'range': range_months,
            **self._common_body(),
        }
        data = self._request('POST', '/yangji-api/api/get-trajectory-v310', json=body)
        if not data:
            return []

        result = []
        for r in data.get('data', []):
            nav_date = date.fromisoformat(r['d'])
            if start_date and nav_date < start_date:
                continue
            if end_date and nav_date > end_date:
                continue
            result.append({
                'nav_date': nav_date,
                'nav': Decimal(str(r['n'])),
                'growth': Decimal(str(r['y'])) * 100,
            })
        return result


# ─── CLI helpers ──────────────────────────────────────────────────────────────

def _colored_growth(growth: Decimal) -> Text:
    s = f'{growth:+.2f}%'
    if growth > 0:
        return Text(s, style='green')
    if growth < 0:
        return Text(s, style='red')
    return Text(s)


def _colored_amount(amount: Decimal) -> Text:
    s = f'{amount:+.2f}'
    if amount > 0:
        return Text(s, style='green')
    if amount < 0:
        return Text(s, style='red')
    return Text(s)


def _get_source() -> XiaoBeiYangJiSource:
    token = load_config().get('token')
    if not token:
        raise click.ClickException('未登录，请先运行: xbyj login')
    source = XiaoBeiYangJiSource()
    source.set_token(token)
    return source


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def main():
    """小倍养基 CLI"""


@main.command()
def login():
    """手机号 + 验证码登录"""
    phone = click.prompt('手机号')
    source = XiaoBeiYangJiSource()
    try:
        source.send_sms(phone)
    except Exception as e:
        raise click.ClickException(f'发送验证码失败: {e}')
    click.echo('验证码已发送')
    code = click.prompt('验证码')
    try:
        result = source.verify_phone(phone, code)
    except Exception as e:
        raise click.ClickException(f'登录失败: {e}')
    save_config({'token': result['token'], 'union_id': result['union_id']})
    click.echo('登录成功')


@main.command()
def logout():
    """清除本地 token"""
    save_config({})
    click.echo('已登出')


@main.command()
@click.argument('codes', nargs=-1, required=True)
def estimate(codes):
    """查询基金估值（支持多个代码）

    示例: xbyj estimate 000001 110022
    """
    source = _get_source()
    table = Table(show_lines=False, highlight=True)
    table.add_column('代码', style='bold')
    table.add_column('名称')
    table.add_column('估算净值', justify='right')
    table.add_column('估算涨跌', justify='right')
    table.add_column('时间', justify='right')

    for code in codes:
        try:
            r = source.fetch_estimate(code)
            if not r:
                table.add_row(code, '-', '-', '-', '-')
                continue
            table.add_row(
                r['fund_code'],
                r['fund_name'],
                str(r['estimate_nav']),
                _colored_growth(r['estimate_growth']),
                r['estimate_time'].strftime('%H:%M:%S'),
            )
        except Exception as e:
            table.add_row(code, Text(f'错误: {e}', style='red'), '-', '-', '-')

    console.print(table)


@main.command()
def holdings():
    """查看当前持仓"""
    source = _get_source()
    try:
        items = source.fetch_holdings()
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无持仓')
        return

    table = Table(show_lines=False, highlight=True)
    table.add_column('代码', style='bold')
    table.add_column('名称')
    table.add_column('份额', justify='right')
    table.add_column('净值', justify='right')
    table.add_column('市值', justify='right')
    table.add_column('盈亏', justify='right')

    for item in items:
        table.add_row(
            item['fund_code'],
            item['fund_name'],
            str(item['share']),
            str(item['nav']),
            str(item['amount']),
            _colored_amount(item['earnings']),
        )

    console.print(table)


@main.command()
@click.argument('code')
@click.option('--start', 'start_date', default=None, metavar='YYYY-MM-DD', help='开始日期')
@click.option('--end', 'end_date', default=None, metavar='YYYY-MM-DD', help='结束日期')
def nav(code, start_date, end_date):
    """查询历史净值

    示例: xbyj nav 000001 --start 2025-01-01 --end 2025-03-01
    """
    source = _get_source()
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError as e:
        raise click.ClickException(f'日期格式错误，请使用 YYYY-MM-DD: {e}')

    try:
        records = source.fetch_nav_history(code, start, end)
    except Exception as e:
        raise click.ClickException(str(e))

    if not records:
        click.echo('无数据')
        return

    table = Table(title=f'{code} 历史净值', show_lines=False)
    table.add_column('日期')
    table.add_column('净值', justify='right')
    table.add_column('涨跌幅', justify='right')

    for r in sorted(records, key=lambda x: x['nav_date']):
        table.add_row(
            r['nav_date'].isoformat(),
            str(r['nav']),
            _colored_growth(r['growth']),
        )

    console.print(table)


@main.command()
def market():
    """查看大盘概览和主要指数"""
    source = _get_source()
    try:
        overview = source.fetch_market_overview()
        indices = source.fetch_market_indices()
    except Exception as e:
        raise click.ClickException(str(e))

    if overview:
        console.print(
            f"北向资金: {overview.get('northbound', 0)}  "
            f"市场成交: {overview.get('market', 0)}  "
            f"情绪: {overview.get('emotion', 0)}"
        )

    if not indices:
        click.echo('暂无指数数据')
        return

    table = Table(title='主要指数', show_lines=False, highlight=True)
    table.add_column('名称', style='bold')
    table.add_column('代码')
    table.add_column('最新点位', justify='right')
    table.add_column('涨跌', justify='right')
    table.add_column('涨跌幅', justify='right')

    for item in indices:
        table.add_row(
            item.get('name', ''),
            item.get('code', ''),
            str(item.get('current', '')),
            str(item.get('chg', '')),
            _colored_growth(Decimal(str(item.get('percent') or 0))),
        )

    console.print(table)


@main.command('sector-hot')
@click.option('--limit', default=10, show_default=True, help='显示数量')
def sector_hot(limit):
    """查看热门板块"""
    source = _get_source()
    try:
        items = source.fetch_sector_heat(limit)
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无数据')
        return

    table = Table(title='热门板块', show_lines=False, highlight=True)
    table.add_column('板块', style='bold')
    table.add_column('代码')
    table.add_column('热度', justify='right')
    table.add_column('涨跌幅', justify='right')

    for item in items:
        table.add_row(
            item.get('sectorName', ''),
            item.get('sectorCode', ''),
            str(item.get('heat', '')),
            _colored_growth(Decimal(str(item.get('changeRate') or 0)) * 100),
        )

    console.print(table)


@main.command('sector-rank')
@click.option('--limit', default=10, show_default=True, help='显示数量')
def sector_rank(limit):
    """查看板块涨幅榜"""
    source = _get_source()
    try:
        items = source.fetch_sector_quote_rank(limit)
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无数据')
        return

    table = Table(title='板块涨幅榜', show_lines=False, highlight=True)
    table.add_column('板块', style='bold')
    table.add_column('代码')
    table.add_column('涨跌幅', justify='right')
    table.add_column('连涨/连跌', justify='right')

    for item in items:
        streak = item.get('streakState') or {}
        streak_type = streak.get('type', '')
        streak_days = streak.get('days', '')
        if streak_type == 'up':
            streak_text = f'连涨{streak_days}天'
        elif streak_type == 'down':
            streak_text = f'连跌{streak_days}天'
        else:
            streak_text = ''
        table.add_row(
            item.get('sectorName', ''),
            item.get('sectorCode', ''),
            _colored_growth(Decimal(str(item.get('changeRate') or 0)) * 100),
            streak_text,
        )

    console.print(table)


@main.command('sector-funds')
@click.argument('sector_code')
@click.option('--limit', default=10, show_default=True, help='显示数量')
def sector_funds(sector_code, limit):
    """查看指定板块的热门基金

    示例: xbyj sector-funds XB1094
    """
    source = _get_source()
    try:
        items = source.fetch_sector_fund_heat(sector_code, limit)
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无数据')
        return

    table = Table(title=f'{sector_code} 热门基金', show_lines=False, highlight=True)
    table.add_column('代码', style='bold')
    table.add_column('名称')
    table.add_column('热度', justify='right')
    table.add_column('涨跌幅', justify='right')

    for item in items:
        table.add_row(
            item.get('fundCode', ''),
            item.get('fundName', ''),
            str(item.get('heat', '')),
            _colored_growth(Decimal(str(item.get('changeRate') or 0)) * 100),
        )

    console.print(table)


@main.command('rank')
@click.option('--type', 'rank_type', type=click.Choice(['quote', 'streak']), default='quote', show_default=True, help='榜单类型')
@click.option('--direction', type=click.Choice(['up', 'down']), default='up', show_default=True, help='上涨/下跌方向')
@click.option('--limit', default=20, show_default=True, help='显示数量')
def rank(rank_type, direction, limit):
    """查看基金涨幅/跌幅榜、连涨/连跌榜"""
    source = _get_source()
    try:
        if rank_type == 'quote':
            data = source.fetch_fund_quote_rank(limit=limit)
            rows = data.get('upList' if direction == 'up' else 'downList', [])
            table = Table(title='基金估值涨幅榜' if direction == 'up' else '基金估值跌幅榜', show_lines=False, highlight=True)
            table.add_column('代码', style='bold')
            table.add_column('名称')
            table.add_column('估值涨跌幅', justify='right')
            table.add_column('所属板块', justify='right')

            for item in rows:
                table.add_row(
                    item.get('fundCode', ''),
                    item.get('fundName', ''),
                    _colored_growth(Decimal(str(item.get('changeRate') or 0)) * 100),
                    item.get('sectorName') or '',
                )
        else:
            data = source.fetch_fund_streak_rank(limit=limit)
            rows = data.get('upList' if direction == 'up' else 'downList', [])
            table = Table(title='基金连涨榜' if direction == 'up' else '基金连跌榜', show_lines=False, highlight=True)
            table.add_column('代码', style='bold')
            table.add_column('名称')
            table.add_column('连涨/连跌天数', justify='right')
            table.add_column('类型', justify='right')
            table.add_column('所属板块', justify='right')

            for item in rows:
                days = item.get('streakDays', '')
                days_text = f'{days}天' if isinstance(days, int) else str(days)
                table.add_row(
                    item.get('fundCode', ''),
                    item.get('fundName', ''),
                    days_text,
                    item.get('firstClass', ''),
                    item.get('sectorName') or '',
                )
    except Exception as e:
        raise click.ClickException(str(e))

    if not rows:
        click.echo('暂无数据')
        return

    console.print(table)


@main.command('news')
@click.option('--page', default=1, show_default=True, help='页码')
@click.option('--limit', 'page_size', default=10, show_default=True, help='每页数量')
def news(page, page_size):
    """查看基金快讯"""
    source = _get_source()
    try:
        items = source.fetch_flash_news(page, page_size)
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无快讯')
        return

    for item in items:
        title = item.get('title') or item.get('content', '')
        if len(title) > 80:
            title = title[:80] + '…'
        publish_time = item.get('publishTime', '')
        click.echo(f'[{publish_time}] {title}')
    click.echo('')


@main.command()
def pick():
    """查看自选列表估值"""
    source = _get_source()
    try:
        items = source.fetch_pick_list()
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无自选')
        return

    table = Table(title='自选列表', show_lines=False, highlight=True)
    table.add_column('代码', style='bold')
    table.add_column('名称')
    table.add_column('估值净值', justify='right')
    table.add_column('估值涨跌', justify='right')

    for item in items:
        nav = Decimal(str(item.get('valuation') or item.get('nav') or 0))
        growth = Decimal(str(item.get('valuationY') or item.get('navY') or 0)) * 100
        table.add_row(
            item.get('code', ''),
            item.get('name', ''),
            str(nav),
            _colored_growth(growth),
        )

    console.print(table)


@main.command('position')
@click.argument('code')
def position(code):
    """查看基金重仓股/行业持仓

    示例: xbyj position 025209
    """
    source = _get_source()
    try:
        data = source.fetch_fund_position_ratio(code)
    except Exception as e:
        raise click.ClickException(str(e))

    rows = data.get('position') or data.get('lastPosition') or []
    if not rows:
        click.echo('暂无持仓数据')
        return

    table = Table(title=f'{code} 基金持仓', show_lines=False, highlight=True)
    table.add_column('代码', style='bold')
    table.add_column('名称')
    table.add_column('权重', justify='right')
    table.add_column('涨跌幅', justify='right')
    table.add_column('行业', justify='right')

    for row in rows:
        table.add_row(
            str(row.get('code') or row.get('stock_code') or ''),
            str(row.get('name') or row.get('stock_name') or ''),
            str(row.get('weight') or ''),
            _colored_growth(Decimal(str(row.get('change') or 0)) * 100) if row.get('change') is not None else '-',
            str(row.get('industry') or ''),
        )

    console.print(table)


@main.command('industry-yield')
@click.argument('codes', nargs=-1, required=True)
def industry_yield(codes):
    """查询行业/指数估值（支持多个代码）

    示例: xbyj industry-yield 886033.TI 000016.SH
    """
    source = _get_source()
    try:
        items = source.fetch_industry_optional_yield(list(codes))
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无数据')
        return

    table = Table(title='行业/指数估值', show_lines=False, highlight=True)
    table.add_column('代码', style='bold')
    table.add_column('最新点位', justify='right')
    table.add_column('涨跌幅', justify='right')

    for item in items:
        table.add_row(
            item.get('code', ''),
            str(item.get('close', '')),
            _colored_growth(Decimal(str(item.get('yield') or 0)) * 100),
        )

    console.print(table)


@main.command('benefits')
def benefits():
    """查看会员权益列表"""
    source = _get_source()
    try:
        items = source.fetch_member_benefits()
    except Exception as e:
        raise click.ClickException(str(e))

    if not items:
        click.echo('暂无数据')
        return

    table = Table(title='会员权益', show_lines=False, highlight=True)
    table.add_column('名称', style='bold')
    table.add_column('描述')
    table.add_column('标签')

    for item in items:
        table.add_row(
            item.get('name', ''),
            item.get('description', ''),
            item.get('promoTag') or item.get('tag') or '',
        )

    console.print(table)


@main.command('messages')
def messages():
    """查看未读消息数"""
    source = _get_source()
    try:
        counts = source.fetch_message_counts()
        system_news = source.fetch_system_news_count()
    except Exception as e:
        raise click.ClickException(str(e))

    if counts:
        for item in counts:
            click.echo(f"{item.get('_id', '')}: {item.get('count', 0)}")
    click.echo(f"系统消息: {system_news}")


@main.command('opportunity')
@click.option('--kind', type=click.Choice(['swing', 'trend', 'reversal', 'dips']), default='swing', show_default=True, help='机会类型')
@click.option('--page', default=1, show_default=True, help='页码')
def opportunity(kind, page):
    """查看基金机会信号（波段/趋势/反转/回撤抄底）"""
    source = _get_source()
    try:
        data = source.fetch_fund_opportunity(kind, page)
    except Exception as e:
        raise click.ClickException(str(e))

    rows = data.get('list', [])
    if not rows:
        click.echo('暂无数据')
        return

    table = Table(title=f'{kind} 机会信号', show_lines=False, highlight=True)
    table.add_column('代码', style='bold')
    table.add_column('名称')
    table.add_column('状态/区域')
    table.add_column('热度', justify='right')

    for item in rows:
        state = item.get('displayState') or item.get('zone') or ''
        table.add_row(
            item.get('code', ''),
            item.get('name', ''),
            state,
            str(item.get('heat', '')),
        )

    console.print(table)


@main.command()
@click.argument('code')
def fund(code):
    """查看基金基本信息

    示例: xbyj fund 025209
    """
    source = _get_source()
    try:
        detail = source._get_fund_detail(code)
    except Exception as e:
        raise click.ClickException(str(e))

    if not detail:
        click.echo('暂无数据')
        return

    click.echo(f"代码: {detail.get('code', code)}")
    click.echo(f"名称: {detail.get('name', '')}")
    click.echo(f"类型: {detail.get('investType', '')}")
    click.echo(f"净值: {detail.get('nav', '')}")
    daily_yield = Decimal(str(detail.get('dailyYield') or 0)) * 100
    click.echo(f"日涨跌: {daily_yield:+.2f}%")
    click.echo(f"成立日: {detail.get('setupDate', '')}")
    click.echo(f"最新净值日期: {detail.get('latestPriceDate', '')}")


@main.command()
def account():
    """查看账户列表和用户信息"""
    source = _get_source()
    try:
        data = source.fetch_account_list()
    except Exception as e:
        raise click.ClickException(str(e))

    user_info = data.get('userInfo') or {}
    if user_info:
        click.echo(f"用户: {user_info.get('nickName', '')} (uid: {user_info.get('uid', '')})")

    accounts = data.get('accountList') or []
    if not accounts:
        click.echo('暂无账户')
        return

    table = Table(title='账户列表', show_lines=False, highlight=True)
    table.add_column('名称', style='bold')
    table.add_column('账户ID', justify='right')
    table.add_column('创建时间')
    table.add_column('更新时间')

    for item in accounts:
        table.add_row(
            item.get('name', ''),
            str(item.get('accountId', '')),
            item.get('createTime', ''),
            item.get('updateTime', ''),
        )

    console.print(table)


if __name__ == '__main__':
    main()
