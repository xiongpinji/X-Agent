"""可直接运行的命令行计算器。

支持：
- 四则运算：+ - * /
- 括号： ( )
- 幂运算： **
- 求余： %
- 常用函数：sqrt, abs, round, pow
- 常量：pi, e

运行方式：python calculator.py
"""

import math
import re
import sys
from typing import List, Union


# ---------- 表达式求值引擎 ----------

def _tokenize(expr: str) -> List[str]:
    """将表达式字符串拆分为 token 列表。"""
    # 数字（含小数与科学计数法）、运算符、括号、函数名
    pattern = re.compile(
        r"\d+\.?\d*(?:[eE][+-]?\d+)?"
        r"|[a-zA-Z_][a-zA-Z0-9_]*"
        r"|[+\-*/%^()]"
    )
    tokens = []
    for m in pattern.finditer(expr):
        tokens.append(m.group(0))
    # 校验是否有多余字符
    cleaned = "".join(pattern.findall(expr)).replace(" ", "")
    original = re.sub(r"\s+", "", expr)
    if cleaned != original:
        raise ValueError(f"无法识别的字符: {expr}")
    return tokens


def _to_postfix(tokens: List[str]) -> List[str]:
    """中缀转后缀（逆波兰），支持一元负号。"""
    precedence = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2, "^": 3}
    right_assoc = {"^"}  # 幂运算右结合
    funcs = {"sqrt", "abs", "round", "pow", "sin", "cos", "tan", "log", "exp"}

    output: List[str] = []
    stack: List[str] = []
    prev_token = None

    for tok in tokens:
        if re.fullmatch(r"\d+\.?\d*(?:[eE][+-]?\d+)?", tok):
            output.append(tok)
        elif tok in funcs:
            stack.append(tok)
        elif tok == "(":
            stack.append(tok)
        elif tok == ")":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
            if stack and stack[-1] == "(":
                stack.pop()
            # 若括号后紧跟函数名，视为函数调用结束，弹出函数
            if stack and stack[-1] in funcs:
                output.append(stack.pop())
        elif tok in precedence:
            # 一元负号处理：若前一个 token 为空或为运算符或左括号，则为一元负号
            if tok == "-" and (
                prev_token is None
                or prev_token in precedence
                or prev_token == "("
                or prev_token in funcs
            ):
                output.append("0")
                output.append(tok)
            else:
                while (
                    stack
                    and stack[-1] in precedence
                    and (
                        precedence[stack[-1]] > precedence[tok]
                        or (
                            precedence[stack[-1]] == precedence[tok]
                            and tok not in right_assoc
                        )
                    )
                ):
                    output.append(stack.pop())
                stack.append(tok)
        else:
            raise ValueError(f"未知的 token: {tok}")
        prev_token = tok

    while stack:
        top = stack.pop()
        if top in "()":
            raise ValueError("括号不匹配")
        output.append(top)
    return output


def _eval_postfix(postfix: List[str]) -> float:
    """求值后缀表达式。"""
    stack: List[float] = []
    funcs = {
        "sqrt": math.sqrt,
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "exp": math.exp,
    }
    for tok in postfix:
        if re.fullmatch(r"\d+\.?\d*(?:[eE][+-]?\d+)?", tok):
            stack.append(float(tok))
        elif tok in funcs:
            if not stack:
                raise ValueError("函数缺少参数")
            arg = stack.pop()
            stack.append(funcs[tok](arg))
        elif tok == "pow":
            if len(stack) < 2:
                raise ValueError("pow 需要两个参数")
            b = stack.pop()
            a = stack.pop()
            stack.append(math.pow(a, b))
        elif tok in "+-*/%^":
            if len(stack) < 2:
                raise ValueError("表达式不完整")
            b = stack.pop()
            a = stack.pop()
            if tok == "+":
                stack.append(a + b)
            elif tok == "-":
                stack.append(a - b)
            elif tok == "*":
                stack.append(a * b)
            elif tok == "/":
                if b == 0:
                    raise ZeroDivisionError("除数不能为零")
                stack.append(a / b)
            elif tok == "%":
                stack.append(a % b)
            elif tok == "^":
                stack.append(a ** b)
        else:
            raise ValueError(f"无法求值: {tok}")
    if len(stack) != 1:
        raise ValueError("表达式无效")
    return stack[0]


# ---------- 常量替换 ----------

CONSTANTS = {"pi": math.pi, "e": math.e}


def _replace_constants(expr: str) -> str:
    """把 pi / e 常量替换为数值（避免被当作函数名）。"""
    result = expr
    for name, value in CONSTANTS.items():
        # 只替换独立的标识符
        result = re.sub(
            rf"\b{name}\b", f"({value})", result
        )
    return result


def evaluate(expression: str) -> float:
    """计算一个数学表达式的值。"""
    if not expression or not expression.strip():
        raise ValueError("表达式为空")
    expr = _replace_constants(expression.strip())
    tokens = _tokenize(expr)
    postfix = _to_postfix(tokens)
    return _eval_postfix(postfix)


# ---------- 交互式主循环 ----------

def _format_result(value: float) -> str:
    """格式化输出结果，去掉多余的零。"""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.10g}"


def main() -> None:
    print("=" * 40)
    print("  命令行计算器")
    print("  支持: + - * / % ^ ( ) 及函数")
    print("  函数: sqrt abs round pow sin cos tan log exp")
    print("  常量: pi, e")
    print("  输入 quit 或 exit 退出")
    print("=" * 40)
    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            print("再见！")
            break
        try:
            result = evaluate(line)
            print(f"= {_format_result(result)}")
        except ZeroDivisionError as exc:
            print(f"错误: {exc}")
        except (ValueError, OverflowError) as exc:
            print(f"错误: {exc}")
        except Exception as exc:  # 兜底
            print(f"错误: {exc}")


if __name__ == "__main__":
    main()
