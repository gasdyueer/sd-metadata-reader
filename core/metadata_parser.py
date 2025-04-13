# core/metadata_parser.py
import os
import json
import re
from PIL import Image
from PIL.PngImagePlugin import PngInfo # 用于潜在的 PNG 元数据访问

# WebUI 详细解析的占位符（实现第 4.3 节中的逻辑）
def parse_prompt1(text: str or dict) -> dict:
    """
    解析通常在 WebUI 生成的图像中找到的“parameters”字符串。
    提取正面提示、负面提示和键值参数。
    现在可以接受字符串或字典作为输入。
    """
    output = {
        'Positive Prompt': 'Not found',
        'Negative Prompt': 'Not found',
        'Steps': 'Not found',
        'Sampler': 'Not found',
        'Schedule type': 'Not found',
        'CFG scale': 'Not found',
        'Seed': 'Not found',
        'Size': 'Not found',
        'Clip skip': 'Not found',
        'Model hash': 'Not found',
        'Model': 'Not found',
        'Version': 'Not found',
        'Module': 'Not found',
        '_Parsing_Errors': []
    }

    try:
        # Handle dictionary input (from get_image_info)
        if isinstance(text, dict):
            if 'Info' in text and 'parameters' in text['Info']:
                text = text['Info']['parameters']
            else:
                output['_Parsing_Errors'].append(
                    "Input dictionary doesn't contain parameters")
                return output

        # Ensure we have a string to work with
        if not isinstance(text, str):
            output['_Parsing_Errors'].append(
                f"Expected string or dict with parameters, got {type(text)}")
            return output

        lines = text.strip().split('\n')
        positive_prompt_lines = []
        negative_prompt_lines = []
        params_lines = []

        # 查找 Negative prompt 和 Steps 的位置
        neg_line_index = -1
        param_line_index = -1
        param_char_index = -1  # 参数在行内的起始字符位置

        neg_prompt_marker = 'Negative prompt:'
        param_start_marker = 'Steps:'

        for i, line in enumerate(lines):
            if neg_line_index == -1:  # 仅查找第一个 Negative prompt
                neg_marker_pos = line.find(neg_prompt_marker)
                if neg_marker_pos != -1:
                    neg_line_index = i
                    # 将 Negative prompt 之前的部分加入 positive
                    positive_prompt_lines.extend(lines[:i])
                    # 将 Negative prompt 所在行的前半部分加入 positive
                    positive_prompt_lines.append(line[:neg_marker_pos].strip())
                    # 将 Negative prompt 所在行的后半部分作为 negative 的开始
                    potential_neg_start = line[neg_marker_pos + len(
                        neg_prompt_marker):].strip()
                    if potential_neg_start:
                        negative_prompt_lines.append(potential_neg_start)

            # 查找第一个 Steps: (通常标志着参数部分的开始)
            if param_line_index == -1:
                param_marker_pos = line.find(param_start_marker)
                if param_marker_pos != -1:
                    param_line_index = i
                    param_char_index = param_marker_pos  # 记录 Steps: 在行内的位置

        # --- 分割逻辑 ---
        if neg_line_index != -1:  # 找到了 Negative prompt
            if param_line_index != -1:  # 同时找到了 Steps:
                if param_line_index == neg_line_index:  # Steps: 和 Negative prompt 在同一行
                    # Negative prompt 内容是 Steps: 之前的部分
                    neg_text_on_line = lines[neg_line_index][
                                       neg_line_index + len(
                                           neg_prompt_marker):param_char_index].strip()
                    if neg_text_on_line:  # 确保不添加空行
                        # 替换之前可能添加的整行后半部分
                        if negative_prompt_lines:
                            negative_prompt_lines[-1] = neg_text_on_line
                        else:
                            negative_prompt_lines.append(neg_text_on_line)

                    # 参数从 Steps: 开始
                    params_lines.append(
                        lines[param_line_index][param_char_index:])
                    params_lines.extend(lines[param_line_index + 1:])
                elif param_line_index > neg_line_index:  # Steps: 在 Negative prompt 之后的行
                    # Negative prompt 内容包括 neg_line_index 的后半部分，以及直到 param_line_index 之前的所有行
                    negative_prompt_lines.extend(
                        lines[neg_line_index + 1: param_line_index])
                    # 参数从 param_line_index 开始
                    params_lines.extend(lines[param_line_index:])
                else:  # Steps: 在 Negative prompt 之前（理论上不太可能，按原样处理）
                    negative_prompt_lines.extend(lines[neg_line_index + 1:])
                    output['_Parsing_Errors'].append(
                        "Warning: 'Steps:' found before 'Negative prompt:'. Parsing might be inaccurate.")
            else:  # 只找到了 Negative prompt，没找到 Steps:
                negative_prompt_lines.extend(lines[neg_line_index + 1:])
        else:  # 没有找到 Negative prompt
            if param_line_index != -1:  # 找到了 Steps:
                positive_prompt_lines.extend(lines[:param_line_index])
                positive_prompt_lines.append(
                    lines[param_line_index][:param_char_index].strip())
                params_lines.append(lines[param_line_index][param_char_index:])
                params_lines.extend(lines[param_line_index + 1:])
            else:  # 既没有 Negative prompt 也没有 Steps:
                positive_prompt_lines = lines

        # 清理和赋值 Prompt
        output['Positive Prompt'] = "\n".join(
            filter(None, positive_prompt_lines)).strip()
        output['Negative Prompt'] = "\n".join(
            filter(None, negative_prompt_lines)).strip()
        if not output['Negative Prompt']:
            output['Negative Prompt'] = 'Not found'

        # --- 解析参数 ---
        if params_lines:
            param_str = "\n".join(params_lines).strip()
            param_regex = r'(\w+(?:\s+\w+)*):\s*("([^"]*)"|([^,]*))\s*(?:,|$)\s*'

            params = re.findall(param_regex, param_str)

            param_dict = {}
            last_pos = 0
            for match in re.finditer(param_regex, param_str):
                key = match.group(1).strip()
                value = match.group(4) if match.group(
                    4) is not None else match.group(3)
                if value is None:
                    value = ""
                cleaned_value = value.strip().strip('"').strip()
                normalized_key = key.lower()
                param_dict[normalized_key] = cleaned_value
                last_pos = match.end()

            remaining_str = param_str[last_pos:].strip()
            if remaining_str:
                output['_Parsing_Errors'].append(
                    f"Warning: Could not parse trailing parameter text: '{remaining_str[:100]}...'")

            # 将解析的参数分配给输出字典
            processed_keys_lower = set()
            for key_out in list(output.keys()):
                if key_out in ['Positive Prompt', 'Negative Prompt',
                               '_Parsing_Errors']:
                    continue
                key_out_lower = key_out.lower()
                if key_out_lower in param_dict:
                    output[key_out] = param_dict[key_out_lower]
                    processed_keys_lower.add(key_out_lower)

            # 存储未在预定义字段中匹配到的参数
            for key_in_lower, val_in in param_dict.items():
                if key_in_lower not in processed_keys_lower:
                    output[f"其他数据: {key_in_lower}"] = val_in

    except Exception as e:
        output['_Parsing_Errors'].append(f"Error parsing WebUI parameters: {e}")
        output['Raw Parameters'] = text

    return output

# ComfyUI 解析的占位符（实现第 4.4 节中的逻辑）
def parse_prompt2(info_dict: dict) -> dict:
    """
    分析元数据字典，专门解析 ComfyUI 相关字段。
    处理“prompt”、“workflow”，如果存在，则调用 parse_prompt1 处理“parameters”。
    """
    parsed_info = {'_Parsing_Errors': []}
    comfy_nodes = {} # {node_title_or_id: {details...}}
    raw_prompt_json = "Not found"
    raw_workflow_json = "Not found"
    parsed_parameters = None

    # 处理已知的 ComfyUI 键和“parameters”
    for k, v in info_dict.items():
        if k == "prompt" and isinstance(v, str):
            raw_prompt_json = v # 存储原始数据
            try:
                prompt_data = json.loads(v)
                parsed_info['Prompt (raw JSON)'] = v[:500] + '...' if len(v) > 500 else v # 截断的原始数据
                if isinstance(prompt_data, dict):
                    parsed_info['Prompt Nodes'] = {}
                    for node_id, node_data in prompt_data.items():
                        title = node_id # 默认为 ID
                        node_details = {'id': node_id}
                        if isinstance(node_data, dict):
                            # 尝试从 _meta 获取标题（如果可用）（常见约定）
                            if '_meta' in node_data and isinstance(node_data['_meta'], dict) and 'title' in node_data['_meta']:
                                title = node_data['_meta']['title']
                            node_details['class_type'] = node_data.get('class_type', 'N/A')
                            node_details['inputs'] = node_data.get('inputs', {})
                            # 存储所有数据以供以后显示（如果需要）
                            node_details['_raw_node_data'] = node_data # 可能很大
                        else:
                             node_details['error'] = "节点数据不是字典"

                        # 使用标题作为用户可见列表的键，存储详细信息
                        comfy_nodes[f"{title} ({node_id})"] = node_details
                else:
                    parsed_info['_Parsing_Errors'].append("ComfyUI 'prompt' 字段不是 JSON 对象（字典）。")
            except json.JSONDecodeError as e:
                parsed_info['_Parsing_Errors'].append(f"Error decoding ComfyUI 'prompt' JSON: {e}")
                parsed_info['Prompt (raw JSON)'] = raw_prompt_json # 错误时显示原始数据

        elif k == "workflow" and isinstance(v, str):
            raw_workflow_json = v # 存储原始数据
            parsed_info['Workflow (raw JSON)'] = v[:500] + '...' if len(v) > 500 else v # 截断的原始数据
            # 可选：如果以后需要，可以在此处添加完整的工作流程解析
            # try:
            #    workflow_data = json.loads(v)
            #    # ... process workflow ...
            # except json.JSONDecodeError as e:
            #    parsed_info['_Parsing_Errors'].append(f"Error decoding ComfyUI 'workflow' JSON: {e}")


        elif k == "parameters" and isinstance(v, str):
            # 找到参数 - 可能是 WebUI 格式或来自 ComfyUI 节点/插件
            parsed_parameters = parse_prompt1(v) # 使用 WebUI 解析器
            parsed_info['Parsed Parameters (from parameters key)'] = parsed_parameters
            if parsed_parameters.get('_Parsing_Errors'):
                 parsed_info['_Parsing_Errors'].extend(parsed_parameters['_Parsing_Errors'])


        elif isinstance(v, str) and len(v) > 500: # 存储截断的其他长字符串
             parsed_info[f'{k} (raw, truncated)'] = v[:500] + '...'
        # elif isinstance(v, (dict, list)): # 避免直接存储大型原始字典/列表
        #     parsed_info[f'{k} (type)'] = type(v).__name__
        else: # 直接存储其他键
            parsed_info[k] = v

    # 将提取的节点添加到主 parsed_info 字典中以进行访问
    parsed_info['_comfy_nodes_extracted'] = comfy_nodes

    return parsed_info


# 获取元数据并识别来源的主要函数（实现 4.5 中的逻辑）
def get_image_metadata(file_path: str) -> dict | None:
    """
    读取图像元数据，识别来源 (WebUI/ComfyUI)，
    并返回包含基本信息、原始信息、
    来源类型和解析数据的结构化字典。
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found - {file_path}")
        return {"error": "File not found"}

    result = {
        'file_path': file_path,
        'error': None,
        'basic_info': {},
        'raw_info': {},
        'source_type': 'Unknown', # 'WebUI', 'ComfyUI', 'ComfyUI_with_Params', 'Unknown'
        'parsed_data': {},
        'comfy_nodes': {} # 专门用于 ComfyUI 节点列表显示
    }

    try:
        with Image.open(file_path) as img:
            # 基本信息 (FR-06)
            result['basic_info']['Format'] = img.format
            result['basic_info']['Size'] = img.size
            result['basic_info']['Mode'] = img.mode

            # 原始信息字典 (FR-07)
            info_dict = {}
            if hasattr(img, 'info') and img.info:
                info_dict = img.info.copy() # 使用副本
            elif isinstance(img, Image.PngImagePlugin.PngImageFile) and hasattr(img, 'text') and img.text:
                 # 如果“info”为空但“text”存在，则处理 PNG 文本块
                 # 有时元数据存储在此处而不是“info”中
                 info_dict = img.text.copy()
            
            # 处理嵌套在Comment字段中的JSON格式元数据
            if 'Comment' in info_dict and isinstance(info_dict['Comment'], str):
                try:
                    comment_data = json.loads(info_dict['Comment'])
                    if isinstance(comment_data, dict):
                        info_dict.update(comment_data)
                except json.JSONDecodeError:
                    pass
            
            result['raw_info'] = info_dict

            # 识别来源（FR-08 和第 4.5 节）
            has_parameters = "parameters" in info_dict and isinstance(info_dict.get("parameters"), str)
            has_prompt = "prompt" in info_dict and isinstance(info_dict.get("prompt"), str)
            has_workflow = "workflow" in info_dict and isinstance(info_dict.get("workflow"), str)

            if has_parameters and not has_prompt and not has_workflow:
                result['source_type'] = 'WebUI'
                # 使用 WebUI 解析器解析 (FR-09, FR-11)
                result['parsed_data'] = parse_prompt1(info_dict["parameters"])
            elif (has_prompt or has_workflow) and not has_parameters:
                result['source_type'] = 'ComfyUI'
                # 使用 ComfyUI 解析器解析 (FR-09, FR-10)
                parsed_info = parse_prompt2(info_dict)
                result['parsed_data'] = parsed_info
                result['comfy_nodes'] = parsed_info.get('_comfy_nodes_extracted', {}) # 获取提取的节点
            elif (has_prompt or has_workflow) and has_parameters:
                result['source_type'] = 'ComfyUI_with_Params'
                 # 使用 ComfyUI 解析器解析，它应该在内部调用 parse_prompt1 处理“parameters”（第 4.5 节）
                parsed_info = parse_prompt2(info_dict)
                result['parsed_data'] = parsed_info
                result['comfy_nodes'] = parsed_info.get('_comfy_nodes_extracted', {}) # 获取提取的节点
            else:
                result['source_type'] = 'Unknown'
                # 未找到特定键，仅显示原始信息（如果可用）
                result['parsed_data'] = {"message": "无法识别来源（未找到 WebUI/ComfyUI 特定键）。"}

            # 在解析的数据中包含原始信息，以便在需要时轻松访问/显示
            result['parsed_data']['_raw_info_dict'] = result['raw_info']


    except FileNotFoundError:
         result['error'] = "处理期间未找到文件。"
         print(f"Error: File not found - {file_path}")
    except Exception as e:
        result['error'] = f"读取或解析元数据时出错: {e}"
        print(f"Error processing {file_path}: {e}")
        # 可选地存储异常详细信息
        result['parsed_data'] = {'_Fatal_Error': str(e)}


    return result

# --- 正则表达式搜索功能（占位符）---
def search_metadata(metadata: dict, pattern: str) -> list:
    """
    使用正则表达式搜索元数据字典中的字符串值。
    返回元组列表：(key_path, list of matches)。
    每个匹配项都是匹配文本的字符串。
    """
    results = []
    if not metadata or not pattern:
        return results
    try:
        regex = re.compile(pattern)
    except re.error as e:
        print(f"Invalid regex: {e}")
        return [("Regex Error", f"Invalid pattern: {e}")]  # Return error as result

    # Simple recursive search for strings in the metadata structure
    def find_matches(data, current_path=""):
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{current_path}.{key}" if current_path else key
                find_matches(value, new_path)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                new_path = f"{current_path}[{index}]"
                find_matches(item, new_path)
        elif isinstance(data, str):
            # Avoid searching excessively long raw strings unless necessary
            # Or maybe only search specific parsed fields? For demo, search all.
            try:
                matches = list(regex.finditer(data))
                if matches:
                    match_strings = []
                    for match in matches:
                        match_strings.append(match.group(0))  # 获取匹配的字符串
                    results.append((current_path, match_strings))  # Path and list of matched strings
            except Exception as e:
                error_message = f"Error during regex search on path {current_path}: {e}"
                print(error_message)  # 使用编译的正则表达式不应经常发生
                results.append((current_path, [error_message])) # 添加错误信息到结果
        else:
            pass # 忽略其他类型

    # find_matches(metadata)  # 在整个元数据中搜索
    find_matches(metadata.get('parsed_data', {}))  # 主要在解析的数据中搜索
    # find_matches(metadata.get('raw_info', {}), "raw_info")

    return results
