#!/usr/bin/python3
# -*- coding: utf8 -*-
"""
# 注意！不支持青龙2.10.3以下版本
# 此脚本需要安装第三方依赖：deepdiff
# 脚本来自 柒月
# 如果请求api.github.com失败请自行想办法，用拉库用的Github加速代理是没用的
# 青龙里面要有监控的Github仓库的拉库命令，通过监控Github仓库来查看是否有新的开卡脚本
# 如果发现新的开卡脚本则自动拉库并运行开卡脚本，如果发现已有多个相同开卡脚本时
# 且其中一个开卡脚本已经运行过了或者正在运行，之后更新的开卡脚本将不会再运行

# 填写要监控的GitHub仓库的 用户名/仓库名/分支/脚本关键词
# 监控多个仓库请用 & 隔开
export GitRepoHost="feverrun/my_scripts/main/jd_opencard"
# http代理，访问不了github的可以填上，无账号密码的直接填“http://ip:端口”
export GitProxy="http://账号:密码@127.0.0.1:8080"
# 运行开卡脚本前禁用开卡脚本定时任务，不填则不禁用，保留原有定时
export opencardDisable="true"

cron: */5 0-3 * * *
new Env('开卡更新检测')
"""

from time import sleep
from notify import send
import requests,deepdiff,json,os

# 获取脚本ID
def qlcron(name):
    url = host+"/crons?searchValue="+name
    rsp = session.get(url=url, headers=headers)
    jsons = rsp.json()
    if rsp.status_code == 200:
        if len(jsons["data"]):
            List.append("获取任务成功："+jsons["data"][0]["name"])
            return jsons["data"][0]["name"],[jsons["data"][0]["_id"]]
        else:
            List.append(f"没有找到任务：{name}")
            return False,False
    else:
        List.append(f'请求青龙失败：{url}')
        if "message" in jsons:
            List.append(f'错误信息：{jsons["message"]}')
        return False,False

def qltoken():
    # 读取青龙登录token
    with open(f"{path}/config/auth.json", 'rb') as json_file:
        authjson = json.load(json_file)
    if "token" in authjson:
        token = authjson["token"]
        return token
    else:
        List.append("青龙Token获取失败")
        return

def qlrun(scripts_name):
    url = host+"/crons/run"
    # 获取仓库任务信息
    RepoName,RepoID = qlcron(GitRepo)
    if not RepoName:
        List.append(f"获取仓库任务信息失败：{GitRepo}")
        return
    # 运行拉取仓库任务
    scriptspath = path+"/scripts/"+GitRepoHost[0]+"_"+GitRepoHost[1]
    if not os.path.exists(scriptspath):
        scriptspath = path+"/scripts/"+GitRepoHost[0]+"_"+GitRepoHost[1]+"_"+GitRepoHost[2]
    File = os.path.exists(scriptspath+"/"+scripts_name)
    while not File:
        List.append("没有找到脚本："+GitRepoHost[0]+"_"+GitRepoHost[1]+"/"+scripts_name)
        rsp = session.put(url=url,headers=headers,data=json.dumps(RepoID))
        if rsp.status_code == 200:
            List.append(f"运行拉库任务：{RepoName}")
        else:
            List.append(f'请求青龙失败：{url}')
            if "message" in rsp.json():
                List.append(f'错误信息：{rsp.json()["message"]}')
            return
        sleep(10)
        File = os.path.exists(scriptspath+"/"+scripts_name)
    else:
        List.append("找到开卡脚本："+GitRepoHost[0]+"_"+GitRepoHost[1]+"/"+scripts_name)
    # 获取开卡任务信息
    TaskName,TaskID = qlcron(scripts_name)
    if not TaskName:
        List.append(f"获取开卡任务信息失败：{scripts_name}")
        return
    # 禁用开卡任务
    if 'opencardDisable' in os.environ:
        Disable = os.environ['opencardDisable']
        if Disable=="true":
            vurl = host+"/crons/disable"
            rsp = session.put(url=vurl,headers=headers,data=json.dumps(TaskID))
            if rsp.status_code == 200:
                List.append(f"禁用开卡任务：{TaskName}")
            else:
                List.append(f'请求青龙失败：{url}')
                if "message" in rsp.json():
                    List.append(f'错误信息：{rsp.json()["message"]}')
                return
    # 查找当前是否有多个同名开卡任务
    namename = TaskName.split(" ")
    if len(namename)>1:
        namename = namename[1]
    else:
        namename = namename[0]
    vurl = host+"/crons?searchValue="+namename
    rsp = session.get(url=vurl, headers=headers).json()
    if len(rsp["data"])>1:
        List.append(f"找到多个任务：{namename}")
        # 查看当前任务是否运行过
        for a in rsp["data"]:
            xurl = host+"/crons/"+a["_id"]
            xrsp = session.get(url=xurl, headers=headers).json()
            if "last_execution_time" in xrsp["data"]:
                List.append("该任务曾运行："+xrsp["data"]["name"])
                List.append("放弃运行任务："+TaskName)
                return
            else:
                List.append("从未运行任务："+xrsp["data"]["name"])
    # 运行开卡任务
    rsp = session.put(url=url,headers=headers,data=json.dumps(TaskID))
    if rsp.status_code == 200:
        List.append(f"运行开卡任务：{TaskName}")
    else:
        List.append(f'请求青龙失败：{url}')
        if "message" in rsp.json():
            List.append(f'错误信息：{rsp.json()["message"]}')

def main():
    state = True
    # 请求Github仓库获取目录树
    rsp = session.get(url=api,headers={"Content-Type":"application/json"},proxies=proxies)
    if rsp.status_code != 200:
        List.append(f'请求GitHub失败：{api}')
        if "message" in rsp.json():
            List.append(f'错误信息：{rsp.json()["message"]}')
        return state
    # 只保存目录树中的开卡脚本的文件名信息
    tree = []
    for x in rsp.json()["tree"]:
        if GitRepoHost[3] in x["path"]:
            tree.append(x["path"])
    # 查看是否有tree.json文件
    if not os.path.exists(f"{path}/scripts/tree_{GitRepoHost[0]}.json"):
        with open(f"{path}/scripts/tree_{GitRepoHost[0]}.json","w") as f:
            json.dump(tree,f)
        List.append(f"没有找到tree_{GitRepoHost[0]}.json文件！将自动生成")
    # 读取上一次保存的tree.json并与当前tree进行对比
    with open(f"{path}/scripts/tree_{GitRepoHost[0]}.json", 'rb') as json_file:
        tree_json = json.load(json_file)
    diff = deepdiff.DeepDiff(tree_json, tree)
    # 判断是否有新增开卡脚本
    if "values_changed" in diff:
        for x in diff["values_changed"]:
            scripts_name = diff["values_changed"][x]["new_value"]
            List.append(f"新增开卡脚本：{scripts_name}")
            # 拉库运行开卡脚本
            qlrun(scripts_name)
            break
    elif "iterable_item_added" in diff:
        for x in diff["iterable_item_added"]:
            scripts_name = diff["iterable_item_added"][x]
            List.append(f"新增开卡脚本：{scripts_name}")
            # 拉库运行开卡脚本
            qlrun(scripts_name)
            break
    else:
        List.append("没有新增开卡脚本")
        state=False
    with open(f"{path}/scripts/tree_{GitRepoHost[0]}.json","w") as f:
        List.append(f"保存数据到tree_{GitRepoHost[0]}.json文件")
        json.dump(tree,f)
    return state

if 'GitRepoHost' in os.environ:
    session = requests.session()
    proxies = {}
    if 'GitProxy' in os.environ:
        proxies['https'] = os.environ['GitProxy']
    host = 'http://127.0.0.1:5700/api'
    RepoHost = os.environ['GitRepoHost'].split("&")
    datapath = os.path.exists("/ql/data")
    print("注意！不支持青龙2.10.3以下版本")
    if datapath:
        print("当前青龙版本高于2.12.0")
        path = "/ql/data"
    else:
        print("当前青龙版本低于2.12.0")
        path = "/ql"
    token = qltoken()
    headers = {
        "Content-Type":"application/json;charset=UTF-8",
        "Authorization":"Bearer "+token
    }
    for RepoX in RepoHost:
        List = []
        GitRepoHost = RepoX.split("/")
        GitRepo = GitRepoHost[0]+"/"+GitRepoHost[1]
        GitBranch = GitRepoHost[2]
        List.append(f"监控仓库：https://github.com/{GitRepo}")
        api = f'https://api.github.com/repos/{GitRepo}/git/trees/{GitBranch}'
        state = main()
        tt = '\n'.join(List)
        print(tt)
        if state:
            send('开卡更新检测', tt)
else:
    print("请查看脚本注释后设置相关变量")
