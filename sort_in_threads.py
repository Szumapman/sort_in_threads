import sys
import os
import shutil
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# additional library requiring installation (pip install cowsay) used to display final information
try:
    import cowsay
except ImportError:
    IS_COWSAY_AVAILABLE = False
else:
    IS_COWSAY_AVAILABLE = True

# the name of the file to which the report is saved (the report is saved in the user home directory)
report_file_name = os.path.join(Path.home(), "sort_report.txt")


def get_path() -> str:
    """
    The function checks whether the user has entered an additional parameter on the command line in the form of a path to the directory he wants to sort out.
    If not, the program terminates, telling the user what the run command should look like with the additional parameter included.
    If the path is correct (leads to the directory) it is returned as a string.

    :rtype: str
    """
    exit_help = f"Stars program with command like: {sys.argv[0]} /user/folder_to_sort/ (path to folder you want to sort)."
    if len(sys.argv) < 2:
        sys.exit(f"Too few command-line arguments.\n{exit_help}")
    elif len(sys.argv) > 2:
        sys.exit(f"Too many command line arguments.\n{exit_help}")
    folder_path = sys.argv[1]
    if os.path.exists(os.path.dirname(folder_path)) and os.path.isdir(folder_path):
        return folder_path
    sys.exit(f"{folder_path} is not a proper folder path.\n{exit_help}")


def prepare_folder(path: str) -> tuple[list, dict]:
    """This function prepares the folder for sorting by creating a list of directories
    and a dictionary of the files where the key is the path and the value is a list of files in this directory.
    Empty directories are deleted.

    Args:
        path (str): path to directory to prepare for sorting

    Returns:
        tuple[list, dict]: list of directories and dictionary of files in the directory
    """
    # list of files and directories located in a given directory
    folder_items = list(os.scandir(path))
    subdirectories = []
    files = []
    for item in folder_items:
        # I check if it's a directory, if so I normalize its name and recursively call the sort_folde function
        if item.is_dir():
            # removal of empty directoriesw
            temp_list = os.listdir(item)
            if len(temp_list) == 0:
                os.rmdir(item.path)
            # skip directories which are excluded from sorting
            if not item.name in [
                "images",
                "video",
                "documents",
                "audio",
                "archives",
            ]:
                dir_name = normalize(item.name)
                dir_path = os.path.join(path, dir_name)  # Path(path, dir_name)
                # I check if there was a change in the directory name after using the normalize function, and if so I move the contents to the directory with the new name
                if dir_name != item.name:
                    # I check if a directory does not already exist that would conflict with the new name, if so I add a numbered version
                    for entry in files:
                        if dir_name == entry.name:
                            dir_path = set_dest_path(os.path.join(path, dir_name))

                    # I move the contents of the renamed directory
                    try:
                        os.renames(os.path.join(path, item.name, dir_path))
                    except FileExistsError:
                        print(
                            f"Directory {dir_name} has not been copied, because too many directories with that name already exist."
                        )
                        continue

                subdirectories.append(dir_path)
        # file operations
        else:
            files.append(item)

    # dictionary with path as a key and list of files to sort as a value
    return subdirectories, {path: files}


def move_files(files_dict: dict) -> tuple[dict, dict, str]:
    """This function moves the files to their respective directories.
    File names are normalized (all characters other than letters and numbers and _ ) are replaced with: _ .
    If a file or directory with the given name already exists, the character _n (where n is the next number) is added to the name.
    Files with specified extensions are moved to appropriate (created as needed) directories in the directory in which they are located
    (e.g., files with .doc extensions are moved to the documents folder, files with .zip extensions are moved to the archives directory, etc.)
    Files with unknown extensions are not moved, but have a normalized name.
    Archives, after being moved to the archives directory, are unzipped to the directory with the name of the archive being unzipped
    (without the extension).
    For each directory, the function saves in the report file (whose name is passed as the second argument), the results of its work.

    Directories to which files with given extensions are moved:
    images -> .jpeg | .png | .jpg | .svg
    video -> .avi | .mp4 | .mov | .mkv
    documents -> .doc | .docx | .txt | .pdf | .xlsx | .pptx
    audio -> .mp3 | .ogg | .wav | .amr
    archives -> .zip | .gz | .tar

    :param path: string with path to directory to be sorted
    :type path: str
    :raise FileNotFoundError: if source path lead to non-existing directory
    :raise NotADirectoryError: if source path lead to file
    :raise FileExistsError: if too many files versions (over 1 000 000) exists in folder

    Args:
        files_dict (dict): dictionary with path as a key and list of files to sort as a value

    Returns:
        tuple[dict, dict, str]: dict of extensions, dict of paths, path of sorted directory
    """
    # logging.debug(f"moving files for folder: {files_dict.keys()}")
    path = list(files_dict)[0]
    files = files_dict[path]

    # auxiliary dictionaries to store data on processed files
    extensions = {
        "images": set(),
        "documents": set(),
        "audio": set(),
        "video": set(),
        "archives": set(),
        "unsorted": set(),
    }
    paths = {
        "images": [],
        "documents": [],
        "audio": [],
        "video": [],
        "archives": [],
        "unsorted": [],
    }

    for file in files:
        file_name, ext = os.path.splitext(file.name)
        file_name = normalize(file_name)
        file_type = ""
        match ext:
            case ".jpeg" | ".png" | ".jpg" | ".svg":
                file_type = "images"
            case ".avi" | ".mp4" | ".mov" | ".mkv":
                file_type = "video"
            case ".doc" | ".docx" | ".txt" | ".pdf" | ".xlsx" | ".pptx":
                file_type = "documents"
            case ".mp3" | ".ogg" | ".wav" | ".amr":
                file_type = "audio"
            case ".zip" | ".gz" | ".tar":
                file_type = "archives"
                # archive is immediately extracted to the folder: archives/"archive name without extension"
                shutil.unpack_archive(
                    os.path.join(path, file.name),
                    os.path.join(path, file_type, file_name),
                )
            case _:
                file_type = "unsorted"

        # I move files (except those with unaccounted-for extensions) to the appropriate directories
        if file_type != "unsorted":
            dest_path = set_dest_path(os.path.join(path, file_type), file_name, ext)
            try:
                os.renames(os.path.join(path, file.name), dest_path)
            except FileExistsError:
                print(
                    f"File {file_name}{ext} has not been copied, because too many files with that name already exist in the destination directory."
                )
                continue

        # adds information about the paths of processed files and their extensions to dicts paths and extensions
        if paths.get(file_type) != None:
            temp_list = paths.get(file_type)
            if file_type == "unsorted":
                temp_list.append(os.path.join(path, file_type, file.name))
            else:
                temp_list.append(
                    f"{os.path.join(path, file_type, file.name)} has moved to: {dest_path}"
                )
            paths.update({file_type: temp_list})
        if extensions.get(file_type) != None:
            temp_set = extensions.get(file_type)
            temp_set.add(ext)
            extensions.update({file_type: temp_set})
    # create_report(extensions, paths, path)
    return extensions, paths, path


def sort_folder(path: str) -> list[tuple[dict, dict, str]]:
    """
    The function sorts files in the directory given as an argument and  its subdirectories (excluding excluded e.g. documents).

    """
    paths_and_files_to_sort = []
    # Call prepare_folder to get subdirectories and files
    subdirectories, files_dict = prepare_folder(path)
    paths_and_files_to_sort.append(files_dict)
    while subdirectories:
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(prepare_folder, subdirectories))
            subdirectories.clear()
            for result in results:
                subdirectories_list, files_dict = result
                subdirectories.extend(subdirectories_list)
                paths_and_files_to_sort.append(files_dict)

    with ThreadPoolExecutor() as executor:
        info_for_report = list(executor.map(move_files, paths_and_files_to_sort))
    return info_for_report


def normalize(name: str) -> str:
    """
    The function normalizes the passed string so that Polish characters are converted to Latin characters,
    and characters other than Latin letters, digits and _ , are converted to _ .

    :param name: The variable with string to normalize
    :type name: str
    :rtype: str
    """
    # Auxiliary dict for the translate() function
    polish_chars = {
        ord("ą"): "a",
        ord("Ą"): "A",
        ord("ć"): "c",
        ord("Ć"): "C",
        ord("ę"): "e",
        ord("Ę"): "E",
        ord("ł"): "l",
        ord("Ł"): "L",
        ord("ń"): "n",
        ord("Ń"): "N",
        ord("ó"): "o",
        ord("Ó"): "O",
        ord("ś"): "s",
        ord("Ś"): "Ś",
        ord("ź"): "z",
        ord("Ż"): "Z",
        ord("ż"): "z",
        ord("Ż"): "Z",
    }
    # I change Polish characters to Latin equivalents on the basis of dict: polish_chars
    normalized_name = name.translate(polish_chars)
    # I change other disallowed characters in the name to the _ character
    normalized_name = re.sub(r"\W+", "_", normalized_name)
    return normalized_name


def set_dest_path(path: str, file_name: str, ext="") -> str:
    """
    A helper function for creating file and directory names.

    :param path: Path to directory
    :type path: str
    :param file_name: Destination directory/file (without extension) name
    :type file_name: str
    :param ext: The extension for file or empty for directory
    :type ext: str
    :rtype: str
    """
    # I check if the given file / directory does not already exist in dest_folder
    full_file_name = f"{file_name}{ext}"
    if os.path.exists(os.path.join(path, full_file_name)):
        # if the file / directory already exists in subsequent versions in dest_folder adds to its name "_n" where i is the first free number from 1 to 1000000
        for i in range(1, 1000000):
            if not os.path.exists(f"{path}{file_name}_{i}{ext}"):
                file_name += f"_{i}"
                break
    full_file_name = f"{file_name}{ext}"
    return os.path.join(path, full_file_name)


def create_report(extensions: dict, paths: dict, path: str):
    """
    The function saves a report with the extensions and files used.

    :param extensions: dict where keys are file categories and values are set with extensions used
    :type extensions: dict
    :param paths: dictionary where the keys are file categories and the values are a list of file paths on which sorting was performed
    :type paths: dict
    :param path: path to the directory on which sorting is performed
    :type path: str
    """
    now = datetime.now()
    with open(report_file_name, "a") as fo:
        fo.write(
            f"{3*'>'} Activity report for directory: {path} - {now.strftime('%Y-%m-%d %H:%M:%S')}:\n"
        )

        # I check to see if there will be information in the given directory to write in the report
        contain_data_to_report = False
        for value in extensions.values():
            if len(value) > 0:
                contain_data_to_report = True
        # if there is data to record I save it
        if contain_data_to_report:
            fo.write(f"Extensions of checked files by category:\n")
            no_transfered_data = True
            for key, values in extensions.items():
                if len(values) > 0:
                    no_transfered_data = False
                    values = list(values)
                    fo.write(f"{key}: {' | '.join(values)};\n")
            if no_transfered_data:
                fo.write(f"{3*'-'}")
            fo.write(f"\nFiles sorted by category:\n")
            for key, values in paths.items():
                if len(values) > 0:
                    no_transfered_data = False
                    fo.write(f"{key}:\n")
                    for value in values:
                        fo.write(f"{value};\n")
            if no_transfered_data:
                fo.write(f"{3*'-'}")
            fo.write(f"\n{20*'-'}\n\n")
        else:
            fo.write("Nothing to sort.\n")


def end_info(path):
    """
    The function outputs an end message to the terminal.

    :param path: path to the directory on which sorting is performed
    :type path: str
    """
    if IS_COWSAY_AVAILABLE:
        cowsay.tux(
            f"I've sorted your files in {path}.\nReport file is here: {report_file_name}"
        )
    else:
        print(
            f"I've sorted your files in {path}.\nReport file is here: {report_file_name}"
        )


def main():
    path = get_path()
    # the name of the file to which the report is saved (the report is saved in the main folder of sorted directory)
    info_for_report = sort_folder(path)
    # create report for each path
    for info in info_for_report:
        create_report(*info)
    # additional information displayed in the console at the end of the program
    end_info(path)


if __name__ == "__main__":
    main()
