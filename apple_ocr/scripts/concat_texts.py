import json
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="从 result.json 按图片拼接文本，生成 {image, text} 列表"
    )
    parser.add_argument("--input", default="result.json", help="输入 JSON 文件，默认 result.json")
    parser.add_argument("--output", default="image_texts.json", help="输出 JSON 文件，默认 image_texts.json")
    parser.add_argument(
        "--sep",
        default="\n",
        help="文本拼接分隔符，默认换行（例如设置为空格：' '）",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        print(f"输入文件不存在: {in_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(in_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取JSON失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("JSON结构错误：应为列表", file=sys.stderr)
        sys.exit(1)

    # 结果：[{image, text}]
    result = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("image")
        items = entry.get("items") or []
        texts = []
        for it in items:
            if not isinstance(it, dict):
                continue
            t = it.get("text")
            if t:
                texts.append(t)
        joined = args.sep.join(texts)
        result.append({"image": name, "text": joined})

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"写出JSON失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()