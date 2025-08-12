import requests
import json
from tqdm import trange

baseurl="https://www.luogu.com.cn/ranking?page="
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'x-lentille-request': 'content-only',
    'x-requested-with': 'XMLHttpRequest'
}

uids=[]

for i in trange(1,21):
    url=f"{baseurl}{i}"
    response = requests.get(url, headers=HEADERS)
    data=json.loads(response.text)['data']["ranking"]["result"]
    for j in range(len(data)):
        uids.append(data[j]["user"]["uid"])
    # 
    # print(json.dumps(data))

print(uids)