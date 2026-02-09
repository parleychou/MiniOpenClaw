import os
import win32com.client as win32
import time

def count_car_blocks():
    file_path = r"E:\2026\20260128_01爱画图\03-建筑平面图.dwg"

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"Target file: {file_path}")
    print("Connecting to AutoCAD...")

    app = None
    # Try different AutoCAD versions
    prog_ids = [
        "AutoCAD.Application.23",  # AutoCAD 2019
        "AutoCAD.Application.24",  # AutoCAD 2020
        "AutoCAD.Application.24.1", # AutoCAD 2021
        "AutoCAD.Application.24.2", # AutoCAD 2022
        "AutoCAD.Application.24.3", # AutoCAD 2023
        "AutoCAD.Application",      # Any version
    ]

    for prog_id in prog_ids:
        try:
            print(f"Trying {prog_id}...")
            app = win32.GetActiveObject(prog_id)
            print(f"Connected to existing AutoCAD instance using {prog_id}")
            break
        except:
            try:
                app = win32.Dispatch(prog_id)
                print(f"Started new AutoCAD instance using {prog_id}")
                break
            except Exception as e:
                continue

    if not app:
        print("Error: Could not connect to AutoCAD. Please ensure AutoCAD is running.")
        print("Try launching AutoCAD manually first, then run this script again.")
        return

    try:
        app.Visible = True

        # Check if file is already open
        doc = None
        for d in app.Documents:
            try:
                if d.FullName.lower() == file_path.lower():
                    doc = d
                    print("File is already open.")
                    break
            except:
                continue

        # Open if not found
        if doc is None:
            print("Opening file...")
            try:
                doc = app.Documents.Open(file_path)
                # Wait for document to fully load
                time.sleep(1)
                doc = app.ActiveDocument
            except Exception as e:
                print(f"Error opening file: {e}")
                # Try to work with active document
                doc = app.ActiveDocument

        if doc:
            try:
                doc_name = doc.Name
            except:
                doc_name = "Unknown"
            print(f"Working with document: {doc_name}")
            doc.Activate()

            count = 0
            found_blocks = []
            print("Scanning for blocks starting with 'car'...")

            # Iterate through ModelSpace
            model_space = doc.ModelSpace
            total_items = model_space.Count
            print(f"Total items in ModelSpace: {total_items}")

            for i in range(total_items):
                try:
                    obj = model_space.Item(i)
                    obj_name = obj.ObjectName

                    if obj_name == "AcDbBlockReference":
                        # Get block name
                        try:
                            name = obj.EffectiveName
                        except:
                            try:
                                name = obj.Name
                            except:
                                continue

                        # Check if name starts with 'car' (case-insensitive)
                        if name and name.lower().startswith('car'):
                            count += 1
                            found_blocks.append(name)
                            print(f"  Found: {name}")
                except Exception as inner_e:
                    continue

            print(f"\n" + "="*50)
            print(f"Result: Found {count} blocks starting with 'car'")
            print("="*50)

            if found_blocks:
                print("\nBlock names found:")
                for block_name in sorted(set(found_blocks)):
                    occurrences = found_blocks.count(block_name)
                    print(f"  - {block_name}: {occurrences} instance(s)")
            else:
                print("\nNo blocks starting with 'car' were found.")
                print("\nNote: This script searches for block names starting with 'car'.")
                print("If your car blocks have a different naming pattern, please let me know.")

        else:
            print("Could not obtain a valid document reference.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    count_car_blocks()
