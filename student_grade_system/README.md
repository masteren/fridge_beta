# 学生成绩管理系统

一个基于命令行的学生成绩管理系统，支持添加、更新、删除、查看学生成绩，并提供统计信息。

## 运行方式

```bash
python student_grade_system.py --help
```

### 添加学生

```bash
python student_grade_system.py add 1001 张三 Math=95 English=88
```

### 更新学生信息

```bash
python student_grade_system.py update 1001 --name 李四 --scores Math=96
```

### 查看学生

```bash
python student_grade_system.py show 1001
```

### 列出所有学生

```bash
python student_grade_system.py list
```

### 统计信息

```bash
python student_grade_system.py stats
```

数据默认保存在同目录下的 `students.json` 文件中。
