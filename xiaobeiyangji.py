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


if __name__ == '__main__':
    main()
