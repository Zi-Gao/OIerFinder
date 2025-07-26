#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import hashlib
import json
import os
import util
from contest import Contest
from oier import OIer
from record import Record
from school import School
from sys import argv, stderr
from tqdm import tqdm
import pickle

import sys
sys.setrecursionlimit(10000)

def __main__():
    gender_map = {"男": 1, "女": -1}
    new_schools = []

    def parse_school_line(line):
        """解析 school.txt 文件的一行。

        line: 一行。
        """

        if line.startswith("#"):  # 注释
            return
        li = line.split(",")
        if len(li) < 3:
            raise ValueError("格式错误")
        province, city, name, *aliases = li
        School.create(name, province, city, aliases)

    def parse_school():
        "解析 school.txt 文件。"

        with open("oierdb-data/data/school.txt") as f:
            raw_data = f.readlines()
        for idx, line in tqdm(enumerate(raw_data), total=len(raw_data)):
            try:
                parse_school_line(line.strip())
            except ValueError as e:
                print(
                    f"\x1b[01mschool.txt:{idx + 1}: \x1b[031merror: \x1b[0;37m'{line.strip()}'\x1b[0m，{e}",
                    file=stderr,
                )

    def parse_raw_line(line):
        """解析 raw.txt 文件的一行。

        line: 一行。
        """

        if line.startswith("#"):  # 注释
            return
        li = line.split(",")
        if len(li) != 9:
            raise ValueError("格式错误")
        contest_name, level, name, grade_name, school_name, score, province, gender_name, identifier = li
        if name == "":
            raise ValueError("姓名不能为空")
        contest = Contest.by_name(contest_name)

        try:
            school = School.by_name(school_name)
        except ValueError as e:
            new_schools.append((province, school_name))
            raise e

        grades = util.get_grades(grade_name)
        gender = gender_map.get(gender_name, 0)
        if not Contest.is_score_valid(score):
            raise ValueError(f"无法识别的分数：\x1b[032m'{score}'\x1b[0m")
        # 开始创建数据
        oier = OIer.of(name, identifier)
        record = contest.add_contestant(oier, score, level, grades, school, province, gender)
        oier.add_record(record)

    def parse_raw():
        "解析 raw.txt 文件。"

        with open("oierdb-data/data/raw.txt") as f:
            raw_data = f.readlines()
        for idx, line in tqdm(enumerate(raw_data), total=len(raw_data)):
            try:
                parse_raw_line(line.strip())
            except ValueError as e:
                print(
                    f"\x1b[01mraw.txt:{idx + 1}: \x1b[31merror: \x1b[0;37m'{line.strip()}'\x1b[0m，{e}",
                    file=stderr,
                )

    def attempt_merge(threshold=240):
        """尝试合并信息。

        threshold: 距离阈值。
        """

        recordseqs = []
        length = OIer.count_all()
        for idx, oier in tqdm(enumerate(OIer.get_all()), total=OIer.count_all()):
            # tqdm
            # 手动合并的无需拆分
            if oier.identifier:
                recordseqs.append(oier.records)
                continue
            original_length = len(oier.records)
            a = [[record] for record in oier.records]
            while True:
                n, best, bi, bj = len(a), threshold + 1, -1, -1
                for i in range(n):
                    for j in range(i):
                        if (dist := Record.distance(a[j], a[i], threshold + 1)) < best:
                            best, bi, bj = dist, j, i
                if best <= threshold:
                    stay_down = Record.check_stay_down(a[bi], a[bj])
                    if stay_down == 1:
                        for record in a[bi]:
                            record.keep_grade()
                    elif stay_down == -1:
                        for record in a[bj]:
                            record.keep_grade()
                    else:
                        assert stay_down == 0
                    a[bi].extend(a[bj])
                    del a[bj]
                else:
                    break
            if "--show-incomplete-merge" in argv and len(a) != 1:
                print(
                    f"\x1b[01;33mwarning: \x1b[0;32m'{oier.name}'\x1b[0m 未完全合并，合并进度为 \x1b[32m{original_length}\x1b[0m → \x1b[32m{len(a)}\x1b[0m",
                    file=stderr,
                )
            recordseqs.extend(a)
        OIer.clear()
        for recordseq in tqdm(recordseqs):
            original = recordseq[0].oier
            # UID 定为该 OIer 首次出现的<b>有效</b>行号
            uid = min(recordseq, key=lambda record: record.id).id
            # 入学年份取众数，相同的话取最早的
            em = util.get_weighted_mode([record.ems for record in recordseq if not record.is_keep_grade()])[0]
            # 性别如果唯一则取之，空或不唯一置空（如跨性别）
            gender = set(record.gender for record in recordseq if record.gender)
            gender = gender.pop() if len(gender) == 1 else 0
            oier = OIer(original.name, original.identifier, gender, em, uid)
            oier.records = recordseq[:]
            for record in oier.records:
                record.oier = oier

    def analyze_individual_oier():
        "分析各体信息。"

        for oier in tqdm(OIer.get_all()):
            oier.compute_ccf_level()
            oier.compute_oierdb_score()

    def merge_schools():
        "合并新增学校信息，输出到 dist/merge_preview.txt 中。"

        nonlocal new_schools
        new_schools = sorted(set(new_schools))
        with open("oierdb-data/dist/merge_preview.txt", "w") as f:
            print(
"""# 用 '#' 号表示注释。
# 这是由 main.py 自动生成的学校合并确认文件，本文件的格式有如下几种：
#   b <name> <origin>  表示将新名称 <name> 合并到 <origin>，将名称作为别名。
#   f <name>,<origin>  表示将新名称 <name> 合并到 <origin>，并将新名称设为正式名称。
#   c <province> <city> <name>  表示插入学校 <province>,<city>,<name>。
#   s <name> <origin>  表示将名称 <name> 从 <origin> 拆出，并按照原来的地区设置新建一个学校。""",
                file=f,
            )
            for province, school_name in tqdm(new_schools):
                res = School.find_candidate(school_name, province)
                method = res[0]
                if method == "b":
                    school = res[1]
                    print(
                        f"\x1b[32m[direct redirect]\x1b[0m: \x1b[35m'{school_name}'\x1b[0m → \x1b[37m'{school.name}'\x1b[0m",
                        file=stderr,
                    )
                    print(f"b {school_name} {school.name}", file=f)
                elif method == "f":
                    school = res[1]
                    print(
                        f"\x1b[32m[name changed]\x1b[0m: \x1b[35m'{school_name}'\x1b[0m ← \x1b[37m'{school.name}'\x1b[0m",
                        file=stderr,
                    )
                    print(f"f {school_name} {school.name}", file=f)
                elif method == "fs":
                    school = res[1]
                    standard = res[2]
                    print(
                        f"\x1b[32m[towards standard name]\x1b[0m: (\x1b[35m'{school_name}'\x1b[0m, \x1b[37m'{school.name}'\x1b[0m) → \x1b[33m'{standard}'\x1b[0m",
                        file=stderr,
                    )
                    print(f"f {standard} {school.name}", file=f)
                    print(f"b {school_name} {school.name}", file=f)
                elif method == "c":
                    city = res[1]
                    print(
                        f"\x1b[32m[create]\x1b[0m: (\x1b[35m'{province}'\x1b[0m, \x1b[35m'{city}'\x1b[0m, \x1b[35m'{school_name}'\x1b[0m)",
                        file=stderr,
                    )
                    print(f"c {province} {city} {school_name}", file=f, end="\n")

    def output_schools():
        "输出学校信息。"

        output = []
        for school in tqdm(School.get_all()):
            output.append([school.name, school.province, school.city, float(round(school.score, 2))])
        with open("dist/school.json", "w", newline="\n") as f:
            json.dump(output, f, ensure_ascii=False)

    def output_compressed():
        "输出压缩的结果，不压缩的结果先咕着。"

        OIer.sort_by_score()
        with open("dist/result.txt", "w", newline="\n") as f:
            for oier in tqdm(OIer.get_all()):
                print(oier.to_compress_format(), file=f, end="\n")

    def compute_sha512():
        """
        计算 dist/result.txt 的 SHA512 值，保存在 sha512/result 中。
        （注：使用 *.txt 后缀可以利用 gzip 压缩）
        """

        file_size = os.stat("oierdb-data/dist/result.txt").st_size

        with open("dist/result.txt", "rb") as f:
            sha512 = hashlib.sha512(f.read()).hexdigest()
        with open("dist/result.info.json", "w", newline="\n") as f:
            print('{"sha512":"' + sha512 + '", "size":' + str(file_size) + "}", file=f)

    def update_static():
        "调用 update_static.js 以产生静态 JSON 信息。"
        if os.name == "nt":  # Windows
            os.system("node update_static.js")
        else:  # Unix-like (Linux, macOS)
            os.system("./update_static.js")

    def report_status(message):
        "向终端报告当前进度。"

        print(f"================ {message} ================", file=stderr)

    report_status("读取学校信息中")
    parse_school()

    report_status("读取选手信息中")
    parse_raw()

    report_status("合并信息中")
    attempt_merge()

    report_status("分析选手中")
    analyze_individual_oier()

    if "--merge-schools" in argv:
        report_status("尝试合并学校中")
        merge_schools()

    def save_all_data():
        """序列化并保存所有数据"""
        # 收集所有数据
        data = {
            'schools': School.get_all(),
            'contests': Contest.get_all(),
            'oiers': OIer.get_all(),
            'records': Record.get_all()
        }
        
        # 增加递归深度限制
        import sys
        sys.setrecursionlimit(10000)
        
        # 保存数据
        with open('data/serialized_data.pkl', 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # 验证保存的数据
        validate_saved_data(data)
        
        print("所有数据已序列化保存到 data/serialized_data.pkl")

    def validate_saved_data(data):
        """验证保存的数据完整性"""
        print("\n序列化前数据验证:")
        oiers = data['oiers']
        records = data['records']
        
        # 检查 OIer 的 records 属性
        oiers_with_id_list = sum(1 for o in oiers if 
                                isinstance(o.records, list) and 
                                all(isinstance(rid, int) for rid in o.records))
        print(f"- 使用ID列表的选手: {oiers_with_id_list}/{len(oiers)}")
        
        # 检查 Record 的对象引用
        records_with_uid = sum(1 for r in records if isinstance(r.oier, int))
        records_with_cid = sum(1 for r in records if isinstance(r.contest, int))
        records_with_sid = sum(1 for r in records if isinstance(r.school, int))
        print(f"- 使用UID引用的记录: {records_with_uid}/{len(records)}")
        print(f"- 使用比赛ID引用的记录: {records_with_cid}/{len(records)}")
        print(f"- 使用学校ID引用的记录: {records_with_sid}/{len(records)}")
        
        # 检查示例数据
        if oiers:
            sample_oier = oiers[0]
            print(f"\n示例选手: {sample_oier.name}")
            print(f"  - records 类型: {type(sample_oier.records)}")
            if sample_oier.records and isinstance(sample_oier.records, list):
                print(f"  - 第一个记录ID: {sample_oier.records[0]}")

    def rebuild_object_references(schools, contests, oiers, records):
        """重建对象间的引用关系"""
        # 创建查找字典
        school_by_id = {s.id: s for s in schools}
        contest_by_id = {c.id: c for c in contests}
        oier_by_uid = {o.uid: o for o in oiers}
        record_by_id = {r.id: r for r in records}
        
        # 重建 Record 对象的引用
        for record in records:
            # 重建 OIer 引用
            if record.oier is not None:
                record.oier = oier_by_uid.get(record.oier)
            
            # 重建 Contest 引用
            if record.contest is not None:
                record.contest = contest_by_id.get(record.contest)
            
            # 重建 School 引用
            if record.school is not None:
                record.school = school_by_id.get(record.school)
        
        # 重建 OIer 对象的 records 列表
        for oier in oiers:
            oier.records = [record_by_id[rid] for rid in oier.records]
        
        # 重建 Contest 对象的 contestants 列表
        for contest in contests:
            contest.contestants = [record_by_id[rid] for rid in contest.contestants]

    report_status("序列化保存数据中")
    save_all_data()

    # report_status("输出到 dist/result.txt 中")
    # output_compressed()

    # report_status("计算 SHA512 摘要中")
    # compute_sha512()

    # report_status("输出学校信息中")
    # output_schools()

    # report_status("输出静态 JSON 信息中")
    # update_static()


if __name__ == "__main__":
    __main__()
