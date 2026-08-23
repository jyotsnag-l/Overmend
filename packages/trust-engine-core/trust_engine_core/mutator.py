import ast
import copy
from typing import List, Dict, Any, Tuple

class NodeReplacer(ast.NodeTransformer):
    def __init__(self, target_mut_id: int, replacement_node: ast.AST):
        self.target_mut_id = target_mut_id
        self.replacement_node = replacement_node

    def visit(self, node: ast.AST) -> ast.AST:
        if getattr(node, "_mut_id", None) == self.target_mut_id:
            # Preserve lineno/col_offset if available
            for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
                if hasattr(node, attr) and not hasattr(self.replacement_node, attr):
                    setattr(self.replacement_node, attr, getattr(node, attr))
            return self.replacement_node
        return self.generic_visit(node)

def label_ast(tree: ast.AST) -> None:
    i = 0
    for node in ast.walk(tree):
        node._mut_id = i
        i += 1

def generate_mutants(file_path: str, source_code: str, target_lines: List[int]) -> List[Dict[str, Any]]:
    """
    Parses source_code and generates a list of mutants targeting the specified lines.
    Each mutant is represented as a dictionary with metadata and mutated source code.
    """
    try:
        tree = ast.parse(source_code)
    except Exception:
        # If the file fails to parse, we cannot generate mutants
        return []

    label_ast(tree)
    mutants = []
    mutant_counter = 1

    # We walk the tree and search for mutable nodes
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", None)
        if lineno is None or lineno not in target_lines:
            continue

        target_mut_id = node._mut_id

        # 1. Comparison operators & Boundaries
        if isinstance(node, ast.Compare):
            # Mutate operators
            for idx, op in enumerate(node.ops):
                replacements = []
                # Comparison operator mutations
                if isinstance(op, ast.Eq):
                    replacements.append((ast.NotEq(), "comparison"))
                elif isinstance(op, ast.NotEq):
                    replacements.append((ast.Eq(), "comparison"))
                elif isinstance(op, ast.Lt):
                    replacements.append((ast.Gt(), "comparison"))
                    replacements.append((ast.LtE(), "boundary"))
                elif isinstance(op, ast.LtE):
                    replacements.append((ast.GtE(), "comparison"))
                    replacements.append((ast.Lt(), "boundary"))
                elif isinstance(op, ast.Gt):
                    replacements.append((ast.Lt(), "comparison"))
                    replacements.append((ast.GtE(), "boundary"))
                elif isinstance(op, ast.GtE):
                    replacements.append((ast.LtE(), "comparison"))
                    replacements.append((ast.Gt(), "boundary"))
                elif isinstance(op, ast.Is):
                    replacements.append((ast.IsNot(), "comparison"))
                elif isinstance(op, ast.IsNot):
                    replacements.append((ast.Is(), "comparison"))
                elif isinstance(op, ast.In):
                    replacements.append((ast.NotIn(), "comparison"))
                elif isinstance(op, ast.NotIn):
                    replacements.append((ast.In(), "comparison"))

                for new_op, category in replacements:
                    # Create a replacement Compare node
                    new_ops = list(node.ops)
                    new_ops[idx] = new_op
                    replacement_node = ast.Compare(
                        left=node.left,
                        ops=new_ops,
                        comparators=node.comparators
                    )
                    mutants.append({
                        "category": category,
                        "node_id": target_mut_id,
                        "line": lineno,
                        "original": ast.unparse(node),
                        "mutated": ast.unparse(replacement_node),
                        "replacement": replacement_node
                    })

        # 2. Boolean operators
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                replacement_node = ast.BoolOp(op=ast.Or(), values=node.values)
                mutants.append({
                    "category": "boolean",
                    "node_id": target_mut_id,
                    "line": lineno,
                    "original": ast.unparse(node),
                    "mutated": ast.unparse(replacement_node),
                    "replacement": replacement_node
                })
            elif isinstance(node.op, ast.Or):
                replacement_node = ast.BoolOp(op=ast.And(), values=node.values)
                mutants.append({
                    "category": "boolean",
                    "node_id": target_mut_id,
                    "line": lineno,
                    "original": ast.unparse(node),
                    "mutated": ast.unparse(replacement_node),
                    "replacement": replacement_node
                })
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            # Mutate 'not x' to 'x'
            replacement_node = node.operand
            mutants.append({
                "category": "boolean",
                "node_id": target_mut_id,
                "line": lineno,
                "original": ast.unparse(node),
                "mutated": ast.unparse(replacement_node),
                "replacement": replacement_node
            })

        # 3. Return values
        elif isinstance(node, ast.Return):
            # Mutate return value
            if node.value is not None:
                # Mutate to None
                if not (isinstance(node.value, ast.Constant) and node.value.value is None):
                    replacement_node = ast.Return(value=ast.Constant(value=None))
                    mutants.append({
                        "category": "return_value",
                        "node_id": target_mut_id,
                        "line": lineno,
                        "original": ast.unparse(node),
                        "mutated": ast.unparse(replacement_node),
                        "replacement": replacement_node
                    })
                # If it's a boolean constant, invert it
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                    inverted = not node.value.value
                    replacement_node = ast.Return(value=ast.Constant(value=inverted))
                    mutants.append({
                        "category": "return_value",
                        "node_id": target_mut_id,
                        "line": lineno,
                        "original": ast.unparse(node),
                        "mutated": ast.unparse(replacement_node),
                        "replacement": replacement_node
                    })
            else:
                # Mutate empty return to return True
                replacement_node = ast.Return(value=ast.Constant(value=True))
                mutants.append({
                    "category": "return_value",
                    "node_id": target_mut_id,
                    "line": lineno,
                    "original": ast.unparse(node),
                    "mutated": ast.unparse(replacement_node),
                    "replacement": replacement_node
                })

        # 4. Arithmetic operators
        elif isinstance(node, ast.BinOp):
            op = node.op
            new_op = None
            if isinstance(op, ast.Add):
                new_op = ast.Sub()
            elif isinstance(op, ast.Sub):
                new_op = ast.Add()
            elif isinstance(op, ast.Mult):
                new_op = ast.Div()
            elif isinstance(op, ast.Div):
                new_op = ast.Mult()
            elif isinstance(op, ast.Mod):
                new_op = ast.Mult()

            if new_op:
                replacement_node = ast.BinOp(left=node.left, op=new_op, right=node.right)
                mutants.append({
                    "category": "arithmetic",
                    "node_id": target_mut_id,
                    "line": lineno,
                    "original": ast.unparse(node),
                    "mutated": ast.unparse(replacement_node),
                    "replacement": replacement_node
                })

        # 5. Indexes
        elif isinstance(node, ast.Subscript):
            # Mutate index e.g. a[i] -> a[i + 1]
            # Since index could be a slice or a standard index, we handle them
            # For simplicity, if it's a simple index:
            slice_node = node.slice
            if not isinstance(slice_node, ast.Slice):
                # Simple index modification: wrap in index + 1
                replacement_slice = ast.BinOp(
                    left=slice_node,
                    op=ast.Add(),
                    right=ast.Constant(value=1)
                )
                replacement_node = ast.Subscript(
                    value=node.value,
                    slice=replacement_slice,
                    ctx=node.ctx
                )
                mutants.append({
                    "category": "indexes",
                    "node_id": target_mut_id,
                    "line": lineno,
                    "original": ast.unparse(node),
                    "mutated": ast.unparse(replacement_node),
                    "replacement": replacement_node
                })
            else:
                # Slice modification: a[lower:upper] -> a[lower + 1:upper]
                if slice_node.lower is not None:
                    replacement_lower = ast.BinOp(
                        left=slice_node.lower,
                        op=ast.Add(),
                        right=ast.Constant(value=1)
                    )
                    replacement_slice = ast.Slice(
                        lower=replacement_lower,
                        upper=slice_node.upper,
                        step=slice_node.step
                    )
                    replacement_node = ast.Subscript(
                        value=node.value,
                        slice=replacement_slice,
                        ctx=node.ctx
                    )
                    mutants.append({
                        "category": "indexes",
                        "node_id": target_mut_id,
                        "line": lineno,
                        "original": ast.unparse(node),
                        "mutated": ast.unparse(replacement_node),
                        "replacement": replacement_node
                    })

    # Prepare final output format and inject unique IDs
    final_mutants = []
    for m in mutants:
        # Reconstruct the full mutated source code for execution
        copied_tree = copy.deepcopy(tree)
        transformer = NodeReplacer(m["node_id"], m["replacement"])
        mutated_tree = transformer.visit(copied_tree)
        ast.fix_missing_locations(mutated_tree)
        mutated_source = ast.unparse(mutated_tree)

        mutant_id = f"mutant_{file_path.replace('/', '_').replace('.', '_')}_{lineno}_{mutant_counter}"
        mutant_counter += 1

        final_mutants.append({
            "id": mutant_id,
            "file": file_path,
            "line": m["line"],
            "category": m["category"],
            "original": m["original"],
            "mutated": m["mutated"],
            "mutated_source": mutated_source
        })

    return final_mutants
