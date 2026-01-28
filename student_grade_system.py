import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


DATA_FILE = Path("students.json")


@dataclass
class Student:
    student_id: str
    name: str
    scores: Dict[str, float]

    @property
    def average(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)


class StudentManager:
    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        self.students: Dict[str, Student] = {}
        self.load()

    def load(self) -> None:
        if not self.data_file.exists():
            self.students = {}
            return
        with self.data_file.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)
        self.students = {
            student_id: Student(
                student_id=student_id,
                name=info["name"],
                scores=info.get("scores", {}),
            )
            for student_id, info in raw_data.items()
        }

    def save(self) -> None:
        serialized = {
            student_id: {"name": student.name, "scores": student.scores}
            for student_id, student in self.students.items()
        }
        with self.data_file.open("w", encoding="utf-8") as file:
            json.dump(serialized, file, ensure_ascii=False, indent=2)

    def add_student(self, student: Student) -> None:
        if student.student_id in self.students:
            raise ValueError(f"学号 {student.student_id} 已存在")
        self.students[student.student_id] = student
        self.save()

    def update_student(
        self,
        student_id: str,
        name: Optional[str],
        scores: Optional[Dict[str, float]],
    ) -> None:
        if student_id not in self.students:
            raise ValueError(f"未找到学号 {student_id}")
        student = self.students[student_id]
        if name is not None:
            student.name = name
        if scores is not None:
            student.scores.update(scores)
        self.save()

    def delete_student(self, student_id: str) -> None:
        if student_id not in self.students:
            raise ValueError(f"未找到学号 {student_id}")
        del self.students[student_id]
        self.save()

    def list_students(self) -> List[Student]:
        return sorted(self.students.values(), key=lambda s: s.student_id)

    def get_student(self, student_id: str) -> Student:
        if student_id not in self.students:
            raise ValueError(f"未找到学号 {student_id}")
        return self.students[student_id]

    def stats(self) -> Dict[str, float]:
        if not self.students:
            return {"count": 0, "average": 0.0}
        averages = [student.average for student in self.students.values()]
        return {
            "count": len(self.students),
            "average": sum(averages) / len(averages),
        }


def parse_scores(scores: List[str]) -> Dict[str, float]:
    parsed: Dict[str, float] = {}
    for score in scores:
        if "=" not in score:
            raise ValueError(
                "成绩格式应为 课程=分数，例如 Math=95"
            )
        course, value = score.split("=", 1)
        parsed[course] = float(value)
    return parsed


def format_student(student: Student) -> str:
    scores = ", ".join(
        f"{course}:{value}" for course, value in student.scores.items()
    )
    return (
        f"学号: {student.student_id}\n"
        f"姓名: {student.name}\n"
        f"成绩: {scores if scores else '暂无'}\n"
        f"平均分: {student.average:.2f}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="学生成绩管理系统")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="添加学生")
    add_parser.add_argument("student_id", help="学号")
    add_parser.add_argument("name", help="姓名")
    add_parser.add_argument(
        "scores", nargs="*", help="课程成绩，例如 Math=95"
    )

    update_parser = subparsers.add_parser("update", help="更新学生信息")
    update_parser.add_argument("student_id", help="学号")
    update_parser.add_argument("--name", help="新的姓名")
    update_parser.add_argument(
        "--scores", nargs="*", help="课程成绩，例如 Math=95"
    )

    delete_parser = subparsers.add_parser("delete", help="删除学生")
    delete_parser.add_argument("student_id", help="学号")

    show_parser = subparsers.add_parser("show", help="查看学生")
    show_parser.add_argument("student_id", help="学号")

    subparsers.add_parser("list", help="列出学生")
    subparsers.add_parser("stats", help="统计信息")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    manager = StudentManager()

    if args.command == "add":
        scores_for_add = parse_scores(args.scores) if args.scores else {}
        student = Student(
            student_id=args.student_id,
            name=args.name,
            scores=scores_for_add,
        )
        manager.add_student(student)
        print("添加成功")
    elif args.command == "update":
        scores_for_update = parse_scores(args.scores) if args.scores else None
        manager.update_student(args.student_id, args.name, scores_for_update)
        print("更新成功")
    elif args.command == "delete":
        manager.delete_student(args.student_id)
        print("删除成功")
    elif args.command == "show":
        student = manager.get_student(args.student_id)
        print(format_student(student))
    elif args.command == "list":
        students = manager.list_students()
        if not students:
            print("暂无学生数据")
            return
        for student in students:
            print(format_student(student))
            print("-" * 20)
    elif args.command == "stats":
        stats = manager.stats()
        print(f"学生数: {stats['count']}")
        print(f"平均分: {stats['average']:.2f}")


if __name__ == "__main__":
    main()
