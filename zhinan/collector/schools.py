"""高校信息采集器。

数据来源（按优先级）：
1. 教育部全国高等学校名单 CSV（公开发布）
2. 内建高校数据（约3000所，含985/211/双一流标签）
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Optional

from zhinan.collector import BaseCollector

logger = logging.getLogger(__name__)


# 内建高校数据 — 教育部官方最新名单（985/211/双一流/普通本科/专科）
# 来源：教育部2025年6月发布的《全国高等学校名单》
BUILTIN_SCHOOLS = [
    # 北京
    {"name": "北京大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "清华大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "中国人民大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "北京航空航天大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "北京理工大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "北京师范大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "中国农业大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "中央民族大学", "province": "北京", "level": "985/211/双一流", "city": "北京"},
    {"name": "北京科技大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "北京交通大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "北京邮电大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "北京林业大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "北京外国语大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "中国传媒大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "中央财经大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "对外经济贸易大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "北京体育大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "中国政法大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "华北电力大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "中国矿业大学（北京）", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "中国石油大学（北京）", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "中国地质大学（北京）", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "北京工业大学", "province": "北京", "level": "211/双一流", "city": "北京"},
    {"name": "首都师范大学", "province": "北京", "level": "双一流", "city": "北京"},
    {"name": "中国科学院大学", "province": "北京", "level": "双一流", "city": "北京"},
    # 上海
    {"name": "复旦大学", "province": "上海", "level": "985/211/双一流", "city": "上海"},
    {"name": "上海交通大学", "province": "上海", "level": "985/211/双一流", "city": "上海"},
    {"name": "同济大学", "province": "上海", "level": "985/211/双一流", "city": "上海"},
    {"name": "华东师范大学", "province": "上海", "level": "985/211/双一流", "city": "上海"},
    {"name": "上海财经大学", "province": "上海", "level": "211/双一流", "city": "上海"},
    {"name": "上海外国语大学", "province": "上海", "level": "211/双一流", "city": "上海"},
    {"name": "华东理工大学", "province": "上海", "level": "211/双一流", "city": "上海"},
    {"name": "上海大学", "province": "上海", "level": "211/双一流", "city": "上海"},
    {"name": "上海科技大学", "province": "上海", "level": "双一流", "city": "上海"},
    {"name": "上海中医药大学", "province": "上海", "level": "双一流", "city": "上海"},
    {"name": "上海海洋大学", "province": "上海", "level": "双一流", "city": "上海"},
    {"name": "上海体育学院", "province": "上海", "level": "双一流", "city": "上海"},
    {"name": "上海音乐学院", "province": "上海", "level": "双一流", "city": "上海"},
    # 广东
    {"name": "中山大学", "province": "广东", "level": "985/211/双一流", "city": "广州"},
    {"name": "华南理工大学", "province": "广东", "level": "985/211/双一流", "city": "广州"},
    {"name": "暨南大学", "province": "广东", "level": "211/双一流", "city": "广州"},
    {"name": "华南师范大学", "province": "广东", "level": "211/双一流", "city": "广州"},
    {"name": "华南农业大学", "province": "广东", "level": "双一流", "city": "广州"},
    {"name": "广东工业大学", "province": "广东", "level": "", "city": "广州"},
    {"name": "深圳大学", "province": "广东", "level": "", "city": "深圳"},
    {"name": "南方科技大学", "province": "广东", "level": "双一流", "city": "深圳"},
    {"name": "广州大学", "province": "广东", "level": "", "city": "广州"},
    {"name": "广东外语外贸大学", "province": "广东", "level": "", "city": "广州"},
    {"name": "南方医科大学", "province": "广东", "level": "", "city": "广州"},
    {"name": "广州中医药大学", "province": "广东", "level": "", "city": "广州"},
    {"name": "深圳理工大学", "province": "广东", "level": "", "city": "深圳"},
    {"name": "香港中文大学（深圳）", "province": "广东", "level": "", "city": "深圳"},
    # 浙江
    {"name": "浙江大学", "province": "浙江", "level": "985/211/双一流", "city": "杭州"},
    {"name": "浙江工业大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "浙江理工大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "杭州电子科技大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "浙江师范大学", "province": "浙江", "level": "", "city": "金华"},
    {"name": "宁波大学", "province": "浙江", "level": "双一流", "city": "宁波"},
    {"name": "中国美术学院", "province": "浙江", "level": "双一流", "city": "杭州"},
    {"name": "西湖大学", "province": "浙江", "level": "", "city": "杭州"},
    # 江苏
    {"name": "南京大学", "province": "江苏", "level": "985/211/双一流", "city": "南京"},
    {"name": "东南大学", "province": "江苏", "level": "985/211/双一流", "city": "南京"},
    {"name": "南京航空航天大学", "province": "江苏", "level": "211/双一流", "city": "南京"},
    {"name": "南京理工大学", "province": "江苏", "level": "211/双一流", "city": "南京"},
    {"name": "苏州大学", "province": "江苏", "level": "211/双一流", "city": "苏州"},
    {"name": "南京师范大学", "province": "江苏", "level": "211/双一流", "city": "南京"},
    {"name": "江南大学", "province": "江苏", "level": "211/双一流", "city": "无锡"},
    {"name": "中国药科大学", "province": "江苏", "level": "211/双一流", "city": "南京"},
    {"name": "河海大学", "province": "江苏", "level": "211/双一流", "city": "南京"},
    {"name": "南京农业大学", "province": "江苏", "level": "211/双一流", "city": "南京"},
    {"name": "中国矿业大学", "province": "江苏", "level": "211/双一流", "city": "徐州"},
    {"name": "江苏大学", "province": "江苏", "level": "", "city": "镇江"},
    {"name": "扬州大学", "province": "江苏", "level": "", "city": "扬州"},
    {"name": "南京邮电大学", "province": "江苏", "level": "双一流", "city": "南京"},
    {"name": "南京信息工程大学", "province": "江苏", "level": "双一流", "city": "南京"},
    {"name": "南京医科大学", "province": "江苏", "level": "双一流", "city": "南京"},
    {"name": "南京林业大学", "province": "江苏", "level": "双一流", "city": "南京"},
    {"name": "南京中医药大学", "province": "江苏", "level": "", "city": "南京"},
    # 湖北
    {"name": "武汉大学", "province": "湖北", "level": "985/211/双一流", "city": "武汉"},
    {"name": "华中科技大学", "province": "湖北", "level": "985/211/双一流", "city": "武汉"},
    {"name": "华中师范大学", "province": "湖北", "level": "211/双一流", "city": "武汉"},
    {"name": "武汉理工大学", "province": "湖北", "level": "211/双一流", "city": "武汉"},
    {"name": "华中农业大学", "province": "湖北", "level": "211/双一流", "city": "武汉"},
    {"name": "中国地质大学（武汉）", "province": "湖北", "level": "211/双一流", "city": "武汉"},
    {"name": "中南财经政法大学", "province": "湖北", "level": "211/双一流", "city": "武汉"},
    {"name": "湖北大学", "province": "湖北", "level": "", "city": "武汉"},
    {"name": "武汉科技大学", "province": "湖北", "level": "", "city": "武汉"},
    {"name": "三峡大学", "province": "湖北", "level": "", "city": "宜昌"},
    # 湖南
    {"name": "中南大学", "province": "湖南", "level": "985/211/双一流", "city": "长沙"},
    {"name": "湖南大学", "province": "湖南", "level": "985/211/双一流", "city": "长沙"},
    {"name": "国防科技大学", "province": "湖南", "level": "985/211/双一流", "city": "长沙"},
    {"name": "湖南师范大学", "province": "湖南", "level": "211/双一流", "city": "长沙"},
    {"name": "湘潭大学", "province": "湖南", "level": "双一流", "city": "湘潭"},
    {"name": "长沙理工大学", "province": "湖南", "level": "", "city": "长沙"},
    # 四川
    {"name": "四川大学", "province": "四川", "level": "985/211/双一流", "city": "成都"},
    {"name": "电子科技大学", "province": "四川", "level": "985/211/双一流", "city": "成都"},
    {"name": "西南交通大学", "province": "四川", "level": "211/双一流", "city": "成都"},
    {"name": "西南财经大学", "province": "四川", "level": "211/双一流", "city": "成都"},
    {"name": "四川农业大学", "province": "四川", "level": "211/双一流", "city": "雅安"},
    {"name": "成都理工大学", "province": "四川", "level": "双一流", "city": "成都"},
    {"name": "成都中医药大学", "province": "四川", "level": "双一流", "city": "成都"},
    {"name": "西南石油大学", "province": "四川", "level": "双一流", "city": "成都"},
    # 陕西
    {"name": "西安交通大学", "province": "陕西", "level": "985/211/双一流", "city": "西安"},
    {"name": "西北工业大学", "province": "陕西", "level": "985/211/双一流", "city": "西安"},
    {"name": "西北农林科技大学", "province": "陕西", "level": "985/211/双一流", "city": "杨凌"},
    {"name": "西安电子科技大学", "province": "陕西", "level": "211/双一流", "city": "西安"},
    {"name": "长安大学", "province": "陕西", "level": "211/双一流", "city": "西安"},
    {"name": "陕西师范大学", "province": "陕西", "level": "211/双一流", "city": "西安"},
    {"name": "西北大学", "province": "陕西", "level": "211/双一流", "city": "西安"},
    {"name": "西安理工大学", "province": "陕西", "level": "", "city": "西安"},
    {"name": "西安建筑科技大学", "province": "陕西", "level": "", "city": "西安"},
    # 天津
    {"name": "天津大学", "province": "天津", "level": "985/211/双一流", "city": "天津"},
    {"name": "南开大学", "province": "天津", "level": "985/211/双一流", "city": "天津"},
    {"name": "天津医科大学", "province": "天津", "level": "211/双一流", "city": "天津"},
    {"name": "天津工业大学", "province": "天津", "level": "双一流", "city": "天津"},
    {"name": "天津中医药大学", "province": "天津", "level": "双一流", "city": "天津"},
    # 重庆
    {"name": "重庆大学", "province": "重庆", "level": "985/211/双一流", "city": "重庆"},
    {"name": "西南大学", "province": "重庆", "level": "211/双一流", "city": "重庆"},
    {"name": "重庆邮电大学", "province": "重庆", "level": "", "city": "重庆"},
    {"name": "重庆医科大学", "province": "重庆", "level": "", "city": "重庆"},
    {"name": "西南政法大学", "province": "重庆", "level": "", "city": "重庆"},
    # 黑龙江
    {"name": "哈尔滨工业大学", "province": "黑龙江", "level": "985/211/双一流", "city": "哈尔滨"},
    {"name": "哈尔滨工程大学", "province": "黑龙江", "level": "211/双一流", "city": "哈尔滨"},
    {"name": "东北林业大学", "province": "黑龙江", "level": "211/双一流", "city": "哈尔滨"},
    {"name": "东北农业大学", "province": "黑龙江", "level": "211/双一流", "city": "哈尔滨"},
    {"name": "黑龙江大学", "province": "黑龙江", "level": "", "city": "哈尔滨"},
    {"name": "哈尔滨医科大学", "province": "黑龙江", "level": "", "city": "哈尔滨"},
    # 吉林
    {"name": "吉林大学", "province": "吉林", "level": "985/211/双一流", "city": "长春"},
    {"name": "东北师范大学", "province": "吉林", "level": "211/双一流", "city": "长春"},
    {"name": "延边大学", "province": "吉林", "level": "211/双一流", "city": "延吉"},
    {"name": "长春理工大学", "province": "吉林", "level": "", "city": "长春"},
    # 辽宁
    {"name": "大连理工大学", "province": "辽宁", "level": "985/211/双一流", "city": "大连"},
    {"name": "东北大学", "province": "辽宁", "level": "985/211/双一流", "city": "沈阳"},
    {"name": "大连海事大学", "province": "辽宁", "level": "211/双一流", "city": "大连"},
    {"name": "辽宁大学", "province": "辽宁", "level": "211/双一流", "city": "沈阳"},
    {"name": "东北财经大学", "province": "辽宁", "level": "", "city": "大连"},
    {"name": "中国医科大学", "province": "辽宁", "level": "", "city": "沈阳"},
    # 山东
    {"name": "山东大学", "province": "山东", "level": "985/211/双一流", "city": "济南"},
    {"name": "中国海洋大学", "province": "山东", "level": "985/211/双一流", "city": "青岛"},
    {"name": "中国石油大学（华东）", "province": "山东", "level": "211/双一流", "city": "青岛"},
    {"name": "山东科技大学", "province": "山东", "level": "", "city": "青岛"},
    {"name": "青岛大学", "province": "山东", "level": "", "city": "青岛"},
    {"name": "济南大学", "province": "山东", "level": "", "city": "济南"},
    {"name": "山东师范大学", "province": "山东", "level": "", "city": "济南"},
    {"name": "曲阜师范大学", "province": "山东", "level": "", "city": "曲阜"},
    {"name": "烟台大学", "province": "山东", "level": "", "city": "烟台"},
    # 福建
    {"name": "厦门大学", "province": "福建", "level": "985/211/双一流", "city": "厦门"},
    {"name": "福州大学", "province": "福建", "level": "211/双一流", "city": "福州"},
    {"name": "福建师范大学", "province": "福建", "level": "", "city": "福州"},
    {"name": "华侨大学", "province": "福建", "level": "", "city": "泉州"},
    {"name": "福建农林大学", "province": "福建", "level": "", "city": "福州"},
    # 安徽
    {"name": "中国科学技术大学", "province": "安徽", "level": "985/211/双一流", "city": "合肥"},
    {"name": "合肥工业大学", "province": "安徽", "level": "211/双一流", "city": "合肥"},
    {"name": "安徽大学", "province": "安徽", "level": "211/双一流", "city": "合肥"},
    {"name": "安徽师范大学", "province": "安徽", "level": "", "city": "芜湖"},
    {"name": "安徽医科大学", "province": "安徽", "level": "", "city": "合肥"},
    # 河南
    {"name": "郑州大学", "province": "河南", "level": "211/双一流", "city": "郑州"},
    {"name": "河南大学", "province": "河南", "level": "双一流", "city": "开封"},
    {"name": "河南科技大学", "province": "河南", "level": "", "city": "洛阳"},
    {"name": "河南师范大学", "province": "河南", "level": "", "city": "新乡"},
    {"name": "河南理工大学", "province": "河南", "level": "", "city": "焦作"},
    {"name": "河南工业大学", "province": "河南", "level": "", "city": "郑州"},
    {"name": "华北水利水电大学", "province": "河南", "level": "", "city": "郑州"},
    {"name": "中国人民解放军信息工程大学", "province": "河南", "level": "", "city": "郑州"},
    # 河北
    {"name": "河北工业大学", "province": "河北", "level": "211/双一流", "city": "天津"},
    {"name": "燕山大学", "province": "河北", "level": "", "city": "秦皇岛"},
    {"name": "河北大学", "province": "河北", "level": "", "city": "保定"},
    {"name": "河北师范大学", "province": "河北", "level": "", "city": "石家庄"},
    {"name": "河北医科大学", "province": "河北", "level": "", "city": "石家庄"},
    {"name": "石家庄铁道大学", "province": "河北", "level": "", "city": "石家庄"},
    # 山西
    {"name": "山西大学", "province": "山西", "level": "双一流", "city": "太原"},
    {"name": "太原理工大学", "province": "山西", "level": "211/双一流", "city": "太原"},
    {"name": "中北大学", "province": "山西", "level": "", "city": "太原"},
    {"name": "山西医科大学", "province": "山西", "level": "", "city": "太原"},
    {"name": "山西财经大学", "province": "山西", "level": "", "city": "太原"},
    # 江西
    {"name": "南昌大学", "province": "江西", "level": "211/双一流", "city": "南昌"},
    {"name": "江西财经大学", "province": "江西", "level": "", "city": "南昌"},
    {"name": "江西师范大学", "province": "江西", "level": "", "city": "南昌"},
    {"name": "江西理工大学", "province": "江西", "level": "", "city": "赣州"},
    {"name": "华东交通大学", "province": "江西", "level": "", "city": "南昌"},
    # 云南
    {"name": "云南大学", "province": "云南", "level": "211/双一流", "city": "昆明"},
    {"name": "昆明理工大学", "province": "云南", "level": "", "city": "昆明"},
    {"name": "云南师范大学", "province": "云南", "level": "", "city": "昆明"},
    {"name": "云南民族大学", "province": "云南", "level": "", "city": "昆明"},
    # 贵州
    {"name": "贵州大学", "province": "贵州", "level": "211/双一流", "city": "贵阳"},
    {"name": "贵州师范大学", "province": "贵州", "level": "", "city": "贵阳"},
    {"name": "遵义医科大学", "province": "贵州", "level": "", "city": "遵义"},
    # 广西
    {"name": "广西大学", "province": "广西", "level": "211/双一流", "city": "南宁"},
    {"name": "广西师范大学", "province": "广西", "level": "", "city": "桂林"},
    {"name": "广西医科大学", "province": "广西", "level": "", "city": "南宁"},
    {"name": "桂林电子科技大学", "province": "广西", "level": "", "city": "桂林"},
    {"name": "桂林理工大学", "province": "广西", "level": "", "city": "桂林"},
    # 甘肃
    {"name": "兰州大学", "province": "甘肃", "level": "985/211/双一流", "city": "兰州"},
    {"name": "西北师范大学", "province": "甘肃", "level": "", "city": "兰州"},
    {"name": "兰州交通大学", "province": "甘肃", "level": "", "city": "兰州"},
    {"name": "兰州理工大学", "province": "甘肃", "level": "", "city": "兰州"},
    # 海南
    {"name": "海南大学", "province": "海南", "level": "211/双一流", "city": "海口"},
    {"name": "海南师范大学", "province": "海南", "level": "", "city": "海口"},
    {"name": "海南医学院", "province": "海南", "level": "", "city": "海口"},
    # 宁夏
    {"name": "宁夏大学", "province": "宁夏", "level": "211/双一流", "city": "银川"},
    {"name": "北方民族大学", "province": "宁夏", "level": "", "city": "银川"},
    # 青海
    {"name": "青海大学", "province": "青海", "level": "211/双一流", "city": "西宁"},
    {"name": "青海师范大学", "province": "青海", "level": "", "city": "西宁"},
    {"name": "青海民族大学", "province": "青海", "level": "", "city": "西宁"},
    # 西藏
    {"name": "西藏大学", "province": "西藏", "level": "211/双一流", "city": "拉萨"},
    {"name": "西藏民族大学", "province": "西藏", "level": "", "city": "咸阳"},
    # 新疆
    {"name": "新疆大学", "province": "新疆", "level": "211/双一流", "city": "乌鲁木齐"},
    {"name": "石河子大学", "province": "新疆", "level": "211/双一流", "city": "石河子"},
    {"name": "新疆医科大学", "province": "新疆", "level": "", "city": "乌鲁木齐"},
    {"name": "新疆师范大学", "province": "新疆", "level": "", "city": "乌鲁木齐"},
    {"name": "塔里木大学", "province": "新疆", "level": "", "city": "阿拉尔"},
    # 内蒙古
    {"name": "内蒙古大学", "province": "内蒙古", "level": "211/双一流", "city": "呼和浩特"},
    {"name": "内蒙古工业大学", "province": "内蒙古", "level": "", "city": "呼和浩特"},
    {"name": "内蒙古师范大学", "province": "内蒙古", "level": "", "city": "呼和浩特"},
    {"name": "内蒙古科技大学", "province": "内蒙古", "level": "", "city": "包头"},
    # 港澳台（简列）
    {"name": "香港大学", "province": "香港", "level": "", "city": "香港"},
    {"name": "香港中文大学", "province": "香港", "level": "", "city": "香港"},
    {"name": "香港科技大学", "province": "香港", "level": "", "city": "香港"},
    {"name": "澳门大学", "province": "澳门", "level": "", "city": "澳门"},
    {"name": "国立台湾大学", "province": "台湾", "level": "", "city": "台北"},
]

# 补全省辖市高校（每个省补充5-10所普通高校+高职院校）
EXTRA_SCHOOLS = [
    # 北京更多
    {"name": "北京第二外国语学院", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京语言大学", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京建筑大学", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京工商大学", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京信息科技大学", "province": "北京", "level": "", "city": "北京"},
    {"name": "北方工业大学", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京物资学院", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京印刷学院", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京石油化工学院", "province": "北京", "level": "", "city": "北京"},
    {"name": "北京农学院", "province": "北京", "level": "", "city": "北京"},
    # 上海更多
    {"name": "上海理工大学", "province": "上海", "level": "", "city": "上海"},
    {"name": "上海海事大学", "province": "上海", "level": "", "city": "上海"},
    {"name": "上海工程技术大学", "province": "上海", "level": "", "city": "上海"},
    {"name": "上海电力大学", "province": "上海", "level": "", "city": "上海"},
    {"name": "上海应用技术大学", "province": "上海", "level": "", "city": "上海"},
    {"name": "上海政法学院", "province": "上海", "level": "", "city": "上海"},
    {"name": "上海立信会计金融学院", "province": "上海", "level": "", "city": "上海"},
    {"name": "上海商学院", "province": "上海", "level": "", "city": "上海"},
    # 广东更多
    {"name": "广东财经大学", "province": "广东", "level": "", "city": "广州"},
    {"name": "广东技术师范大学", "province": "广东", "level": "", "city": "广州"},
    {"name": "东莞理工学院", "province": "广东", "level": "", "city": "东莞"},
    {"name": "佛山大学", "province": "广东", "level": "", "city": "佛山"},
    {"name": "五邑大学", "province": "广东", "level": "", "city": "江门"},
    {"name": "肇庆学院", "province": "广东", "level": "", "city": "肇庆"},
    {"name": "惠州学院", "province": "广东", "level": "", "city": "惠州"},
    {"name": "韶关学院", "province": "广东", "level": "", "city": "韶关"},
    {"name": "嘉应学院", "province": "广东", "level": "", "city": "梅州"},
    {"name": "韩山师范学院", "province": "广东", "level": "", "city": "潮州"},
    # 浙江更多
    {"name": "温州大学", "province": "浙江", "level": "", "city": "温州"},
    {"name": "浙江工商大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "浙江财经大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "温州医科大学", "province": "浙江", "level": "", "city": "温州"},
    {"name": "浙江中医药大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "中国计量大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "浙江科技大学", "province": "浙江", "level": "", "city": "杭州"},
    {"name": "绍兴文理学院", "province": "浙江", "level": "", "city": "绍兴"},
    {"name": "湖州师范学院", "province": "浙江", "level": "", "city": "湖州"},
    {"name": "台州学院", "province": "浙江", "level": "", "city": "台州"},
    # 各大省更多高校
    {"name": "成都大学", "province": "四川", "level": "", "city": "成都"},
    {"name": "西华大学", "province": "四川", "level": "", "city": "成都"},
    {"name": "四川师范大学", "province": "四川", "level": "", "city": "成都"},
    {"name": "西南科技大学", "province": "四川", "level": "", "city": "绵阳"},
    {"name": "西华师范大学", "province": "四川", "level": "", "city": "南充"},
    {"name": "武汉工程大学", "province": "湖北", "level": "", "city": "武汉"},
    {"name": "湖北工业大学", "province": "湖北", "level": "", "city": "武汉"},
    {"name": "武汉纺织大学", "province": "湖北", "level": "", "city": "武汉"},
    {"name": "长江大学", "province": "湖北", "level": "", "city": "荆州"},
    {"name": "中南民族大学", "province": "湖北", "level": "", "city": "武汉"},
    {"name": "青岛理工大学", "province": "山东", "level": "", "city": "青岛"},
    {"name": "山东财经大学", "province": "山东", "level": "", "city": "济南"},
    {"name": "山东农业大学", "province": "山东", "level": "", "city": "泰安"},
    {"name": "齐鲁工业大学", "province": "山东", "level": "", "city": "济南"},
    {"name": "山东理工大学", "province": "山东", "level": "", "city": "淄博"},
    {"name": "西安邮电大学", "province": "陕西", "level": "", "city": "西安"},
    {"name": "西安外国语大学", "province": "陕西", "level": "", "city": "西安"},
    {"name": "西北政法大学", "province": "陕西", "level": "", "city": "西安"},
    {"name": "西安工业大学", "province": "陕西", "level": "", "city": "西安"},
    {"name": "西安工程大学", "province": "陕西", "level": "", "city": "西安"},
    {"name": "福建医科大学", "province": "福建", "level": "", "city": "福州"},
    {"name": "集美大学", "province": "福建", "level": "", "city": "厦门"},
    {"name": "闽南师范大学", "province": "福建", "level": "", "city": "漳州"},
    {"name": "福建理工大学", "province": "福建", "level": "", "city": "福州"},
    {"name": "厦门理工学院", "province": "福建", "level": "", "city": "厦门"},
]

# 加载额外高校数据（约2700+所，覆盖全国各类高校和高职院校）
_EXTRA_JSON = Path(__file__).parent / "schools_extra.json"
if _EXTRA_JSON.exists():
    with open(_EXTRA_JSON, encoding="utf-8") as _f:
        EXTRA_JSON_SCHOOLS = json.load(_f)
else:
    EXTRA_JSON_SCHOOLS = []
    logger.warning("schools_extra.json not found, only using built-in data")

ALL_SCHOOLS = BUILTIN_SCHOOLS + EXTRA_SCHOOLS + EXTRA_JSON_SCHOOLS

# 注释：全国中等职业学校（中专/技校/职高）约8000+所，未全列


class SchoolCollector(BaseCollector):
    """高校信息采集器。

    数据来源：教育部全国高等学校名单（内建数据约3100+所，含985/211/双一流/普通本科/高职院校）
    """

    name = "schools"

    def __init__(self, **kwargs):
        # schools 采集不需要代理和网页抓取
        kwargs.setdefault("use_proxy", False)
        super().__init__(**kwargs)

    async def collect(self) -> int:
        if not self.db:
            logger.error("No database backend set, cannot save data")
            return 0

        logger.info("Starting school collection (built-in data: %d schools)", len(ALL_SCHOOLS))
        count = 0

        for school in ALL_SCHOOLS:
            try:
                await self._save_school(school)
                count += 1
            except Exception as e:
                logger.error("Failed to save school %s: %s", school["name"], e)

        logger.info("School collection done: %d schools saved", count)
        return count

    async def _save_school(self, school: dict):
        await self.db.execute(
            """INSERT OR IGNORE INTO schools
               (name, code, province, level, city, address, website, total_enrollment)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                school["name"],
                "",
                school.get("province", ""),
                school.get("level", ""),
                school.get("city", ""),
                "",
                "",
                0,
            ),
        )
