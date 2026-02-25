from xtquant import xtconstant as const
from xtquant import xtQuantApi

# 登录
api = xtQuantApi.XtQuantApi()
ret = api.login("13818181818", "123456")

# 查询除权除息信息
ret, data = api.query_dividend_data(code="sz.000001", year="2015", yearType="report")

# 打印输出
print(data)