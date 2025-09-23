import json
import requests
from tqdm import trange,tqdm

PRIZE_BASE_URL="https://www.luogu.com.cn/offlinePrize/getList"

UA = 'OlerFinder-Bot/1.0 (+https://github.com/Zi-Gao/OIerFinder)'

BASE_HEADER = {
    'User-Agent': UA
}

def requestPrizeList(uid):
    url=f"{PRIZE_BASE_URL}/{uid}"
    response = requests.get(url, headers=BASE_HEADER)
    return response

def getPrizeList(uid):
    prize=[]
    res=requestPrizeList(uid)

    try:
        data=json.loads(res.text)["prizes"]
        for pri in data:
            prize.append(pri["prize"])
    except Exception as e:
        tqdm.write(res.status_code,res.text)
    return prize

def getPrizes(uids):
    result={}
    for uid in tqdm(uids):
        result[uid]=getPrizeList(uid)

    return result

def findUserCount():
    l=1826585
    r=1826586
    while requestPrizeList(r).status_code==200:
        l=r
        r*=2


    while l<r:
        mid=(l+r)//2
        if requestPrizeList(mid).status_code==200:
            l=mid+1
        else:
            r=mid
    return l-1

RANK_BASE_URL="https://www.luogu.com.cn/ranking?page="
RANK_HEADER = {
    'User-Agent': UA,
    'x-lentille-request': 'content-only',
    'x-requested-with': 'XMLHttpRequest'
}

def getRankPage(i):
    uids=[]
    url=f"{RANK_BASE_URL}{i}"
    response = requests.get(url, headers=RANK_HEADER)
    data=json.loads(response.text)['data']["ranking"]["result"]
    for j in range(len(data)):
        uids.append(data[j]["user"]["uid"])
    return uids

def getTop1000User():
    uids=[]
    for i in trange(1,21):
        uids+=getRankPage(i)
    return uids

if __name__=="__main__":
    print(getPrizeList(10703))