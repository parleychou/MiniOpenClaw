"""
DWG车位统计工具
统计建筑平面图DWG文件中所有以'car'开头的图块（车位）
"""

import win32com.client
import os

def count_car_blocks(dwg_path):
    """
    统计DWG文件中以'car'开头的图块数量

    Args:
        dwg_path: DWG文件路径

    Returns:
        dict: 包含car图块详细信息的字典
    """
    try:
        # 连接AutoCAD
        print("正在连接AutoCAD...")
        acad = win32com.client.Dispatch("AutoCAD.Application")

        # 规范化路径
        dwg_path = os.path.abspath(dwg_path)
        print(f"正在打开文件: {dwg_path}")

        # 检查文件是否已打开
        doc = None
        for d in acad.Documents:
            if d.FullName.upper() == dwg_path.upper():
                doc = d
                print("文件已在AutoCAD中打开")
                break

        # 如果未打开，则打开文件
        if doc is None:
            print("正在打开DWG文件...")
            doc = acad.Documents.Open(dwg_path)

        print(f"当前文档: {doc.Name}")

        # 获取模型空间
        model_space = doc.ModelSpace

        # 统计图块
        print("\n正在扫描图块...")
        print("(这可能需要一些时间，请稍候...)")

        # 统计以car开头的图块引用
        car_blocks = {}
        total_car_count = 0
        processed = 0

        # 获取对象数量
        try:
            total_objects = model_space.Count
            print(f"模型空间对象总数: {total_objects}")
        except:
            total_objects = 0

        for obj in model_space:
            try:
                processed += 1
                if processed % 100 == 0:
                    print(f"已处理: {processed}/{total_objects} 个对象...")

                # 检查是否为块参照
                object_name = obj.ObjectName
                if object_name == 'AcDbBlockReference':
                    # 获取图块名称（使用EffectiveName处理动态块）
                    try:
                        block_name = obj.EffectiveName
                    except:
                        block_name = obj.Name

                    # 检查是否以car开头（不区分大小写）
                    if block_name and block_name.lower().startswith('car'):
                        if block_name not in car_blocks:
                            car_blocks[block_name] = 0
                        car_blocks[block_name] += 1
                        total_car_count += 1
            except Exception as e:
                # 跳过无法访问的对象
                continue

        # 获取块定义信息
        print("\n正在获取块定义信息...")
        blocks_dict = doc.Blocks
        block_details = {}

        for block_name in car_blocks.keys():
            try:
                block_obj = blocks_dict.Item(block_name)
                # 获取块中的对象数量
                obj_count = 0
                try:
                    obj_count = block_obj.Count
                except:
                    pass

                block_details[block_name] = {
                    'count': car_blocks[block_name],
                    'is_xref': block_obj.IsXRef if hasattr(block_obj, 'IsXRef') else False,
                    'is_layout': block_obj.IsLayout if hasattr(block_obj, 'IsLayout') else False,
                    'object_count': obj_count
                }
            except Exception as e:
                block_details[block_name] = {
                    'count': car_blocks[block_name],
                    'error': str(e)
                }

        return {
            'total_count': total_car_count,
            'blocks': block_details,
            'block_types': len(car_blocks)
        }

    except Exception as e:
        print(f"错误: {e}")
        return None

def main():
    # DWG文件路径
    dwg_file = r"E:\2026\20260128_01爱画图\03-建筑平面图.dwg"

    print("=" * 60)
    print("DWG车位统计工具")
    print("=" * 60)
    print(f"目标文件: {dwg_file}")
    print("-" * 60)

    result = count_car_blocks(dwg_file)

    if result:
        print("\n" + "=" * 60)
        print("统计结果")
        print("=" * 60)
        print(f"\n车位总数: {result['total_count']} 个")
        print(f"图块类型数: {result['block_types']} 种")

        if result['blocks']:
            print("\n详细信息:")
            print("-" * 60)
            print(f"{'图块名称':<30} {'数量':<10} {'类型':<15}")
            print("-" * 60)

            for block_name, info in result['blocks'].items():
                block_type = "普通图块"
                if info.get('is_xref'):
                    block_type = "外部参照"
                elif info.get('is_layout'):
                    block_type = "布局图块"

                print(f"{block_name:<30} {info['count']:<10} {block_type:<15}")

        print("=" * 60)
    else:
        print("\n统计失败，请检查：")
        print("1. AutoCAD是否已安装")
        print("2. 文件路径是否正确")
        print("3. 文件是否被其他程序占用")

if __name__ == "__main__":
    main()
