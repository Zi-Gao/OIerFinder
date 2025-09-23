from tqdm import trange
import json
from utils import luogu_crawl


top1000=luogu_crawl.getTop1000User()


f=open("luogu_user.txt","w")
json.dump(luogu_crawl.getPrizes(top1000),f,ensure_ascii=False)