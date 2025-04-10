# core/metadata_parser.py
import os
import json
import re
from PIL import Image
from PIL.PngImagePlugin import PngInfo # 用于潜在的 PNG 元数据访问

# WebUI 详细解析的占位符（实现第 4.3 节中的逻辑）
def parse_prompt1(text: str) -> dict:
    """
    解析通常在 WebUI 生成的图像中找到的“parameters”字符串。
    提取正面提示、负面提示和键值参数。
    （基于提供的示例的简化实现）
    """
    output = {
        'Positive Prompt': 'Not found',
        'Negative Prompt': 'Not found',
        'Steps': 'Not found',
        'Sampler': 'Not found',
        'CFG scale': 'Not found',
        'Seed': 'Not found',
        'Size': 'Not found',
        # 根据需要添加其他常见参数
        '_Parsing_Errors': []
    }
    try:
        lines = text.strip().split('\n')
        positive_prompt_lines = []
        negative_prompt_lines = []
        params_lines = []
        current_section = 'positive' # 默认假设

        # 基本部分拆分
        neg_prompt_marker = 'Negative prompt:'
        params_marker_heuristic = 'Steps:' # 启发式查找参数开始

        param_line_index = -1
        neg_line_index = -1

        for i, line in enumerate(lines):
            if line.startswith(neg_prompt_marker):
                neg_line_index = i
                break
            if params_marker_heuristic in line:
                 # 粗略的启发式：查找包含常见参数键的第一行
                 test_params = re.findall(r'(\w+(?: \w+)*):\s*(".*?"|\S+)', line)
                 if test_params:
                     param_line_index = i
                     # 暂时不要中断，负面提示可能在后面

        # 根据发现确定部分
        if neg_line_index != -1:
            positive_prompt_lines = lines[:neg_line_index]
            # 处理负面提示内容在同一行的情况
            neg_parts = lines[neg_line_index].split(neg_prompt_marker, 1)
            if len(neg_parts) > 1 and neg_parts[1].strip():
                negative_prompt_lines.append(neg_parts[1].strip())
            # 检查在参数开始之前是否有更多行
            potential_param_start = neg_line_index + 1
            if param_line_index != -1 and param_line_index > potential_param_start:
                 negative_prompt_lines.extend(lines[potential_param_start:param_line_index])
                 params_lines = lines[param_line_index:]
            elif param_line_index == -1: # 启发式在否定提示后未找到参数
                 negative_prompt_lines.extend(lines[potential_param_start:])
            else: # param_line_index 必须 <= neg_line_index（例如，否定提示最后）
                 params_lines = lines[param_line_index:neg_line_index] # 这种情况不太常见


        elif param_line_index != -1: # 找到参数，但没有负面提示
            positive_prompt_lines = lines[:param_line_index]
            params_lines = lines[param_line_index:]
        else: # 没有负面提示，没有明确的参数 = 假设所有都是正面提示
             positive_prompt_lines = lines

        output['Positive Prompt'] = "\\n".join(positive_prompt_lines).strip()
        output['Negative Prompt'] = "\\n".join(negative_prompt_lines).strip()
        if not output['Negative Prompt']:
             output['Negative Prompt'] = 'Not found' # 明确说明


        # 解析键值参数字符串
        if params_lines:
            param_str = "\\n".join(params_lines).strip()
             # 用于查找键值对的正则表达式，处理带引号的值和其中潜在的逗号
            # 改进的正则表达式尝试：处理简单情况，可能需要更强的鲁棒性
            param_regex = r'([\\w\\s]+):\\s*(\\"(?:\\\\.|[^\\"\\\\])*\\"|[^,]+(?:,?\\s*[\\w\\s]+:\\s*.*)*?)\\s*(?:,|$)'
            params = re.findall(r'(\\w+(?:\\s\\w+)*):\\s*(\\"(?:\\\\.|[^\\"\\\\])*\\"|[^,]+)', param_str)

            param_dict = {}
            # 基本解析，可能需要改进以处理复杂值
            raw_params = param_str.split(',')
            current_key = None
            current_val = ''
            for item in raw_params:
                parts = item.split(':', 1)
                if len(parts) == 2 and parts[0].strip(): # 找到一个潜在的键
                    if current_key: # 存储先前的键值
                         param_dict[current_key.strip()] = current_val.strip().strip('\"')
                    current_key = parts[0]
                    current_val = parts[1]
                elif current_key: # 继续先前的值
                    current_val += ',' + item

            if current_key: # 存储最后一个键值
                 param_dict[current_key.strip()] = current_val.strip().strip('\"')


            # 将解析的参数分配给输出，处理大小写变体
            processed_keys = set()
            for key_out in output:
                 if key_out in ['Positive Prompt', 'Negative Prompt', '_Parsing_Errors']:
                     continue
                 key_out_lower = key_out.lower()
                 found = False
                 for key_in, val_in in param_dict.items():
                     if key_in.lower() == key_out_lower:
                         output[key_out] = val_in
                         processed_keys.add(key_in)
                         found = True
                         break
                 # 存储未在输出字典中明确列出的剩余键
            for key_in, val_in in param_dict.items():
                if key_in not in processed_keys:
                    output[f"Other: {key_in}"] = val_in # 添加前缀以避免名称冲突


    except Exception as e:
        output['_Parsing_Errors'].append(f"Error parsing WebUI parameters: {e}")
        output['Raw Parameters'] = text # 错误时存储原始文本

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
