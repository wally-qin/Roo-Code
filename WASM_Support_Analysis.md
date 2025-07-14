# WASM 文件支持分析报告

## 问题概述

在 `dist_assets.spec.ts` 中验证的 WASM 文件（如 `tree-sitter-toml.wasm`）与 Python `code_index` 模块的实际支持之间存在不一致。

## 详细分析

### JavaScript/TypeScript 端支持的语言 (WASM 文件)

在 `src/__tests__/dist_assets.spec.ts` 中，测试验证了以下 tree-sitter WASM 文件的存在：

```
tree-sitter-bash.wasm
tree-sitter-cpp.wasm
tree-sitter-c_sharp.wasm
tree-sitter-css.wasm
tree-sitter-c.wasm
tree-sitter-elisp.wasm
tree-sitter-elixir.wasm
tree-sitter-elm.wasm
tree-sitter-embedded_template.wasm
tree-sitter-go.wasm
tree-sitter-html.wasm
tree-sitter-javascript.wasm
tree-sitter-java.wasm
tree-sitter-json.wasm
tree-sitter-kotlin.wasm
tree-sitter-lua.wasm
tree-sitter-objc.wasm
tree-sitter-ocaml.wasm
tree-sitter-php.wasm
tree-sitter-python.wasm
tree-sitter-ql.wasm
tree-sitter-rescript.wasm
tree-sitter-ruby.wasm
tree-sitter-rust.wasm
tree-sitter-scala.wasm
tree-sitter-solidity.wasm
tree-sitter-swift.wasm
tree-sitter-systemrdl.wasm
tree-sitter-tlaplus.wasm
tree-sitter-toml.wasm  ⚠️
tree-sitter-tsx.wasm
tree-sitter-typescript.wasm
tree-sitter-vue.wasm
tree-sitter.wasm
tree-sitter-yaml.wasm
tree-sitter-zig.wasm
```

**总计：36 种语言支持**

### Python code_index 端实际支持的语言

在 `wally_qin/code_index/processors/code_parser.py` 中，只导入并初始化了以下 tree-sitter 语言：

```python
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_rust
import tree_sitter_go
import tree_sitter_java
import tree_sitter_cpp
import tree_sitter_c
```

**总计：仅 8 种语言支持**

### 支持的文件扩展名

在 `constants/__init__.py` 中定义了支持的文件扩展名：

```python
SUPPORTED_EXTENSIONS = {
    ".tla", ".js", ".jsx", ".ts", ".vue", ".tsx", ".py",
    ".rs", ".go", ".c", ".h", ".cpp", ".hpp", ".cs", 
    ".rb", ".java", ".php", ".swift", ".sol", ".kt", 
    ".kts", ".ex", ".exs", ".el", ".html", ".htm", 
    ".md", ".markdown", ".json", ".css", ".rdl", 
    ".ml", ".mli", ".lua", ".scala", ".toml", ".zig", 
    ".elm", ".ejs", ".erb"
}
```

**注意：`.toml` 被列在支持的扩展名中，但没有对应的 tree-sitter 解析器！**

## 主要问题

### 1. TOML 文件支持不完整

- ✅ JavaScript 端：有 `tree-sitter-toml.wasm` 文件
- ✅ Python 端：`.toml` 在 `SUPPORTED_EXTENSIONS` 中
- ❌ Python 端：缺少 `tree_sitter_toml` 导入和初始化
- ❌ Python 端：缺少 `toml_queries.py` 文件

### 2. 大量语言缺失

Python 端缺少以下语言的 tree-sitter 支持：

**配置文件类**
- TOML (`.toml`)
- YAML (`.yaml`, `.yml`)
- JSON (`.json`)

**Web 技术**
- CSS (`.css`)
- HTML (`.html`, `.htm`)
- Vue (`.vue`)

**编程语言**
- C# (`.cs`)
- Ruby (`.rb`)
- PHP (`.php`)
- Swift (`.swift`)
- Kotlin (`.kt`, `.kts`)
- Scala (`.scala`)
- Lua (`.lua`)
- Zig (`.zig`)
- Elm (`.elm`)

**其他**
- Bash/Shell
- Elixir (`.ex`, `.exs`)
- OCaml (`.ml`, `.mli`)
- 以及更多...

### 3. 查询文件不匹配

在 `processors/queries/` 目录中，只有以下查询文件：
- ✅ python_queries.py
- ✅ javascript_queries.py  
- ✅ typescript_queries.py
- ✅ rust_queries.py
- ✅ go_queries.py
- ✅ java_queries.py
- ✅ cpp_queries.py
- ✅ c_queries.py
- ✅ csharp_queries.py (但没有对应的导入)
- ✅ ruby_queries.py (但没有对应的导入)
- ✅ php_queries.py (但没有对应的导入)

**缺失的查询文件包括 `toml_queries.py`**

## 影响

### 对 TOML 文件的影响

当前 TOML 文件会：
1. 被识别为支持的文件类型（因为在 `SUPPORTED_EXTENSIONS` 中）
2. 但无法进行语法感知的解析（缺少 tree-sitter 支持）
3. 可能回退到通用的文本分块处理
4. 失去结构化代码分析的优势

### 对其他语言的影响

类似地，许多其他语言文件虽然有对应的 WASM 文件，但在 Python 端缺少支持，导致：
- 解析质量下降
- 无法提取语法结构
- 搜索和索引效果不佳

## 建议解决方案

### 1. 短期解决方案

对于 TOML 文件：
```python
# 添加到 code_parser.py 的导入部分
import tree_sitter_toml

# 添加到 language_map
'toml': Language(tree_sitter_toml.language()),
```

创建 `toml_queries.py` 文件。

### 2. 长期解决方案

1. **完整的语言支持迁移**：为所有有 WASM 文件的语言添加 Python 支持
2. **依赖管理**：确保所有 tree-sitter 语言包都在 requirements.txt 中
3. **测试对齐**：添加 Python 端的语言支持测试
4. **文档更新**：明确说明支持的语言列表

### 3. 立即行动项

1. 确认是否安装了 `tree-sitter-toml` Python 包
2. 检查其他缺失的 tree-sitter 语言包
3. 更新 `code_parser.py` 以包含所有可用的语言
4. 创建对应的查询文件

## 结论

确实存在问题：**TOML 文件虽然在支持的扩展名列表中，但缺少实际的 tree-sitter 解析支持**，这导致了功能不完整。这个问题不仅影响 TOML，还影响了许多其他在 JavaScript 端有 WASM 支持但在 Python 端缺失的语言。