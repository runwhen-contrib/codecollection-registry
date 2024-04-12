import re
import yaml
import shutil
import fnmatch
import subprocess
import os   
import requests
import jinja2
from collections import Counter
import datetime


from robot.api import TestSuite


github_token = os.getenv('GITHUB_TOKEN')
headers = {}


# YAML file path
yaml_file_path = 'codecollections.yaml'

# Directory where to clone the repositories
clone_dir = './cloned_repos'

# Mkdocs config dirs
mkdocs_root='cc-registry'
docs_dir='docs'

# Tags
all_support_tags = []
support_tags_to_remove = []

#Global CodeCollection Stats
## collection['slug'] is used as the unique key
all_codecollection_stats={}



def parse_robot_file(fpath):
    """
    Parses a robot file in to a python object that is
    json serializable, representing all kinds of interesting
    bits and pieces about the file contents (for UI purposes).
    """
    suite = TestSuite.from_file_system(fpath)
    # pprint.pprint(dir(suite))
    ret = {}
    ret["doc"] = suite.doc  # The doc string
    ret["type"] = suite.name.lower()
    ret["tags"] = []

    for k, v in suite.metadata.items():
        if k.lower() in ["author", "name"]:
            ret[k.lower()] = v
        if k.lower() in ["display name", "name"]:
            ret["display_name"] = v
        if k.lower() in ["supports"]:
            support_tags = re.split('\s*,\s*|\s+', v.strip().upper())
            ret["support_tags"] = support_tags
            all_support_tags.extend(support_tags)
    
    tasks = []
    for task in suite.tests:
        tags = [str(tag) for tag in task.tags if tag not in ["skipped"]]
        # print (task.body)
        tasks.append(
            {
                "id": task.id,
                "name": task.name,
                # "tags": tags,
                "doc": str(task.doc),
                "keywords": task.body
            }
        )
        ret["tags"] = list(set(ret["tags"] + tags))
    ret["tasks"] = tasks
    resourcefile = suite.resource
    ret["imports"] = []
    for i in resourcefile.imports:
        ret["imports"].append(i.name)
    return ret

def find_files(directory, pattern):
    """
    Search for files given directory and its subdirectories matching a pattern.

    Args:
        directory (str): The path of the directory to search.

    Returns:
        A list of file paths that match the search criteria.
    """
    matches = []
    for root, dirnames, filenames in os.walk(directory):
        for filename in fnmatch.filter(filenames, pattern):
            matches.append(os.path.join(root, filename))
    return matches

def clone_repository(git_url, clone_directory, ref='main'):
    """
    Clone a git repository to a specified directory, with an option to specify a reference.
    The reference can be a branch, tag, or commit SHA.
    
    Parameters:
    - git_url: URL of the git repository to clone.
    - clone_directory: The directory where the repository should be cloned.
    - ref: The name of the reference to clone. This can be a branch name, tag, or commit SHA. Defaults to 'main'.
    """
    if not os.path.exists(clone_directory):
        os.makedirs(clone_directory)
    subprocess.run(['git', 'clone', '-b', ref, '--single-branch', git_url], cwd=clone_directory)


def read_yaml(file_path):
    """
    Read a YAML file and return the data.
    """
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def generate_cc_list(data):
    """
    Generate Markdown content based on the provided data and a Jinja2 template file.
    """
    cc_list_template_file_name=f"./{mkdocs_root}/templates/cc-list-template.j2"
    cc_list_markdown_content = ""
    cc_list_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    cc_list_jinja_template = cc_list_jinja_env.get_template(cc_list_template_file_name)
    cc_list_content = cc_list_jinja_template.render(
        data=data,
        all_codecollection_stats=all_codecollection_stats
    )
    with open(f'{mkdocs_root}/{docs_dir}/all_codecollections.md', 'w') as md_file:
        md_file.write(cc_list_content)
    cc_index_template_file_name=f"./{mkdocs_root}/templates/cc-index-template.j2"
    cc_index_markdown_content = ""
    cc_index_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    cc_index_jinja_template = cc_index_jinja_env.get_template(cc_index_template_file_name)
    for codecollection in data['codecollections']: 
        # print(codecollection)
        cc_index_file_path=f'{mkdocs_root}/{docs_dir}/CodeCollection/{codecollection["slug"]}/index.md'
        cc_index_content = cc_index_jinja_template.render(
            codecollection=codecollection,
            codecollection_stats=all_codecollection_stats[codecollection['slug']]
        )
        with open(cc_index_file_path, 'w') as md_file:
            md_file.write(cc_index_content)
    # for collection in data.get('codecollections', []):
    #     markdown_content += jinja_template.render(**collection)
    # return cc_list_content

def clean_path(path):
    """
    Deletes the specified path, including all its contents if it is a directory,
    or the file itself if it's just a file.
    """
    # Check if the path exists
    if os.path.exists(path):
        # Check if the path is a directory
        if os.path.isdir(path):
            # Remove the directory and all its contents
            shutil.rmtree(path)
            print(f"Directory '{path}' has been removed along with all its contents.")
        else:
            # It's a file, remove it
            os.remove(path)
            print(f"File '{path}' has been removed.")
    else:
        print(f"The path '{path}' does not exist.")

def count_directories_at_depth_one(path):
    # List everything in the given path
    items = os.listdir(path)
    # Count only those items which are directories
    directory_count = sum(os.path.isdir(os.path.join(path, item)) for item in items)
    return directory_count

def generate_codebundle_content(collection, clone_path):
    """
    Generate Markdown content based on the provided codebundle data and a Jinja2 template file.
    """
    codecollection=collection["git_url"].split('/')[-1].replace('.git', '')
    codecollection_path = f'{mkdocs_root}/{docs_dir}/CodeCollection/{codecollection}/'
    clean_path(codecollection_path)

    # Update the dictionary with the new or incremented count
    codebundle_count = count_directories_at_depth_one(f"{clone_path}/{codecollection}/codebundles")
    all_codecollection_stats[f"{collection['slug']}"]['total_codebundles'] += codebundle_count

    runbook_template_file_name=f"./{mkdocs_root}/templates/codebundle-runbook-template.j2"
    runbook_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    runbook_jinja_template = runbook_jinja_env.get_template(runbook_template_file_name)
    runbook_files=find_files(f"{clone_path}/{codecollection}/codebundles", 'runbook.robot')
    for runbook in runbook_files: 
        codebundle=runbook.split('/')[5]

        # Reset Genrules and Cheatsheet flags
        has_genrules = "false"
        found_in_cheatsheet = "false"
        raises_issues = "false"

        # Find any genrules
        gen_rules=find_files(f"{clone_path}/{codecollection}/codebundles/{codebundle}/.runwhen/generation-rules", '*.yaml')
        if gen_rules != []: 
            has_genrules = "true"

        # Generate the directory path
        meta_path=f'{clone_path}/{codecollection}/codebundles/{codebundle}/meta.yaml'
        # print(meta_path)
        dir_path = f'{mkdocs_root}/docs/CodeCollection/{codecollection}/{codebundle}'
        # Ensure the directory exists
        os.makedirs(dir_path, exist_ok=True)
        parsed_runbook = parse_robot_file(runbook)
        runbook_source_url = f'{collection["git_url"]}/blob/main/codebundles/{codebundle}/runbook.robot'
        codecollection_total_tasks = all_codecollection_stats[f"{collection['slug']}"]['total_tasks'] + len(parsed_runbook["tasks"])
        all_codecollection_stats[f"{collection['slug']}"]['total_tasks']=codecollection_total_tasks
        meta = {"commands": []}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as file:
                    meta = yaml.safe_load(file)
            except yaml.YAMLError as e:
                print(f"Error loading YAML file: {e}")
            except Exception as e:
                print(f"Error reading file: {e}")
        for task in parsed_runbook["tasks"]:
            # Determine if any tasks are rendered in the cheatsheet
            for keyword in task['keywords']:
                if hasattr(keyword, 'name'):
                    for item in ['render_in_commandlist=true', 'show_in_rwl_cheatsheet=true']:
                        if item in keyword.args:
                          found_in_cheatsheet = "true"
                    for item in ['set_issue_title']:
                        if item in keyword.args:
                          raises_issues = "true"
                    for item in ['RW.CLI.Parse', 'RW.Core.Add Issue']:
                        if item in keyword.name:
                          raises_issues = "true"

            task_name_generalized = task["name"].replace('${', '').replace('}', '')
            task["task_name_generalized"] = task_name_generalized
            task["name_snake_case"] = re.sub(r'\W+', '_', task_name_generalized.lower())
            for command in meta["commands"]:
                if command["name"] == task["name_snake_case"]:
                    task["meta_explanation"] = command["explanation"]
                    # Use .get() with a default of None or an empty string if you prefer
                    useful_scenarios = command.get("when_is_it_useful", None)
                    if useful_scenarios:
                        task["meta_useful_scenarios"] = useful_scenarios

                
        # print(parsed_runbook)
        file_path = os.path.join(dir_path, f'tasks.md')
        runbook_codebundle_content = runbook_jinja_template.render(
            codecollection_slug=collection['slug'],
            runbook_source_url=runbook_source_url,
            parsed_runbook=parsed_runbook, 
            meta=meta, 
            total_tasks=len(parsed_runbook["tasks"]),
            file_path=file_path.replace(f'{mkdocs_root}/{docs_dir}', '').strip('.md'),
            has_genrules=has_genrules,
            found_in_cheatsheet=found_in_cheatsheet,
            raises_issues=raises_issues
        )
        with open(file_path, 'w') as md_file:
            md_file.write(runbook_codebundle_content)

    sli_template_file_name=f"./{mkdocs_root}/templates/codebundle-sli-template.j2"
    sli_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    sli_jinja_template = sli_jinja_env.get_template(sli_template_file_name)
    sli_files=find_files(f"{clone_path}/{codecollection}", 'sli.robot')
    for sli in sli_files: 
        codebundle=sli.split('/')[5]
        gen_rules=find_files(f"{clone_path}/{codecollection}/codebundles/{codebundle}/.runwhen/generation-rules", '*.yaml')
        has_genrules = "false"
        if gen_rules != []: 
            has_genrules = "true"
        # Generate the directory path
        dir_path = f'{mkdocs_root}/{docs_dir}/CodeCollection/{codecollection}/{codebundle}'
        # Ensure the directory exists
        os.makedirs(dir_path, exist_ok=True)
        parsed_sli=parse_robot_file(sli)
        sli_source_url = f'{collection["git_url"]}/blob/main/codebundles/{codebundle}/sli.robot'
        codecollection_total_tasks = all_codecollection_stats[f"{collection['slug']}"]['total_tasks'] + len(parsed_sli["tasks"])
        all_codecollection_stats[f"{collection['slug']}"]['total_tasks']=codecollection_total_tasks
        # print(sli)
        file_path = os.path.join(dir_path, 'health.md')
        sli_codebundle_content = sli_jinja_template.render(
            codecollection_slug=collection['slug'],
            sli_source_url=sli_source_url,
            parsed_sli=parsed_sli, 
            total_tasks=len(parsed_sli["tasks"]),
            file_path=file_path.replace(f'{mkdocs_root}/{docs_dir}', '').strip('.md'),
            has_genrules=has_genrules
        )
        with open(file_path, 'w') as md_file:
            md_file.write(sli_codebundle_content)

    # readme_template_file_name="./cc-index/templates/codebundle-readme-template.j2"
    # readme_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    # readme_jinja_template = readme_jinja_env.get_template(readme_template_file_name)
    # readme_files=find_files(f'{clone_path}/{codecollection}/codebundles/', 'README.md')
    # for readme in readme_files: 
    #     print(readme)
    #     codebundle=readme.split('/')[5]
    #     # Generate the directory path
    #     dir_path = f'cc-index/docs/CodeCollection/{codecollection}/{codebundle}'
    #     # Ensure the directory exists
    #     os.makedirs(dir_path, exist_ok=True)
    #     if os.path.exists(readme):
    #         with open(readme, 'r', encoding='utf-8') as file:
    #             readme_md_contents = file.read()
    #             readme_content = readme_jinja_template.render(
    #                 readme_content=readme_md_contents
    #             )
    #         file_path = os.path.join(dir_path, 'readme.md')
    #         with open(file_path, 'w') as md_file:
    #             md_file.write(readme_content)

def generate_index(all_support_tags_freq, all_codecollection_stats, codecollections_yaml): 
    index_path = f'{mkdocs_root}/{docs_dir}/index.md'
    home_path = f'{mkdocs_root}/{docs_dir}/overrides/home.html'
    index_template_file = f"{mkdocs_root}/templates/index-template.j2"
    home_template_file = f"{mkdocs_root}/templates/home-template.j2"
    index_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    home_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    index_template = index_env.get_template(index_template_file)
    home_template = home_env.get_template(home_template_file)
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    top_10_support_tags = all_support_tags_freq.most_common(10)
    top_10_support_tag_names = [tag for tag, freq in top_10_support_tags]
    tag_icon_url_map = load_icon_urls_for_tags(
        top_10_support_tag_names
    )    
    tags_with_icons = [{
        "name": tag,
        "icon_url": tag_icon_url_map.get(tag)
    } for tag in top_10_support_tag_names]

    total_contributors = sum(item['total_contributors'] for item in all_codecollection_stats.values())
    total_tasks = sum(item['total_tasks'] for item in all_codecollection_stats.values())
    total_codebundles = sum(item['total_codebundles'] for item in all_codecollection_stats.values())
    index_output = index_template.render(
        codecollections=codecollections_yaml.get('codecollections', []),
        tags_with_icons=tags_with_icons,
        total_codebundles=total_codebundles,
        total_tasks=total_tasks,
        total_contributors=total_contributors
    )
    home_output = home_template.render(
        total_codebundles=total_codebundles,
        total_tasks=total_tasks,
        total_contributors=total_contributors
    )

    with open(index_path, 'w') as index_file:
        index_file.write(index_output)
    index_file.close()

    with open(home_path, 'w') as home_file:
        home_file.write(home_output)
    home_file.close()

def load_icon_urls_for_tags(tags, filename="map-tag-icons.yaml", default_url="https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/tag.svg"):
    """
    Load icon URLs for given tags from a YAML file, with a default URL for unmapped tags.

    :param tags: A single tag or a list of tags to find icon URLs for.
    :param filename: The path to the YAML file.
    :param default_url: The default icon URL to use for tags not found in the map.
    :return: A dictionary of tags to their icon URLs.
    """
    # Ensure tags is a list
    if isinstance(tags, str):
        tags = [tags]
    
    tag_icon_url_map = {}
    try:
        with open(filename, "r") as file:
            data = yaml.safe_load(file)
            icons = data.get("icons", [])
            for tag in tags:
                # Initialize each tag with a default URL
                tag_icon_url_map[tag] = default_url
                for icon in icons:
                    if tag in icon.get("tags", []):
                        # Update with specific URL if found
                        tag_icon_url_map[tag] = icon.get("url")
                        break
    except FileNotFoundError:
        print(f"File {filename} not found.")
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}")
    
    return tag_icon_url_map


def generate_github_stats(collection): 
    # If the 'GITHUB_TOKEN' environment variable exists, add it as a Bearer token
    if github_token:
        headers['Authorization'] = f'Bearer {github_token}'
    github_api_url="https://api.github.com"
    owner=collection["git_url"].split('/')[-2]
    repo=collection["git_url"].split('/')[-1].replace('.git', '')
    github_repo_api_url = f'{github_api_url}/repos/{owner}/{repo}/contributors'
    github_repo_api_contributors_url = f'{github_api_url}/repos/{owner}/{repo}/contributors'
    contributors = requests.get(github_repo_api_contributors_url, headers=headers).json()
    all_codecollection_stats[f"{collection['slug']}"]={
            'total_contributors': len(contributors),
            'contributors': [contributor['login'] for contributor in contributors],
            'total_tasks': 0,
            'total_codebundles': 0
    }

    # all_codecollection_stats[f"{collection['slug']}"]['total_contributors']=len(contributors)
    # all_codecollection_stats[f"{collection['slug']}"]['contributors']=[contributor['login'] for contributor in contributors]

def update_footer(): 
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    build_date_path = f'{mkdocs_root}/{docs_dir}/overrides/partials/build_date.html'
    build_date_template_file = f"{mkdocs_root}/templates/build_date.j2"
    build_date_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    build_date_template = build_date_env.get_template(build_date_template_file)
    build_date_output = build_date_template.render(
        current_date=current_date
    )
    with open(build_date_path, 'w') as build_date_file:
        build_date_file.write(build_date_output)
    build_date_file.close()


def main():
    """
    Reads in the registry.yaml file to parse robot files and generate an index.  
    Written out into a local markdown file and served by mkdocs for local dev use.

    Uses markdown extensions from https://facelessuser.github.io/pymdown-extensions/  

    Args:
        args (str): The path the output contents from map-builder. 
    """
    data = read_yaml(yaml_file_path)
    clean_path(clone_dir)
    clean_path(f"{mkdocs_root}/{docs_dir}/CodeCollection")

    for collection in data.get('codecollections', []):
        print(f"Cloning {collection['name']}...")
        org= collection["git_url"].split("/")[-2]
        ref = collection.get('git_ref', 'main')
        clone_path=os.path.join(clone_dir, org)
        clone_repository(collection['git_url'], clone_path, ref)
        generate_github_stats(collection)
        generate_codebundle_content(collection, clone_path)
    
    cc_list_content = generate_cc_list(data)
    # with open(f'{mkdocs_root}/{docs_dir}/all_codecollections.md', 'w') as md_file:
    #     md_file.write(cc_list_content)

    ## Should clean this up. we are pulling from Robot "support tags"
    ## but calling them category tags in the app. 
    # Remove specific tags from all_tags
    for tag_to_remove in support_tags_to_remove:
        all_support_tags.discard(tags_to_remove)  # discard does not raise an error if the element is not found


    all_support_tags_freq = Counter(all_support_tags)

    # Sort Global Tags
    # If you need a deduplicated list of tags, you can extract keys from the Counter
    deduplicated_support_tags = list(all_support_tags_freq.keys())

    # Sorted list of unique tags, if needed
    sorted_support_tags = sorted(deduplicated_support_tags)
    directory_path = os.path.join(mkdocs_root, docs_dir, 'Categories')
    clean_path(directory_path)

    for support_tag in sorted_support_tags: 
        directory_path = os.path.join(mkdocs_root, docs_dir, 'Categories')
        os.makedirs(directory_path, exist_ok=True)
        icon_url = load_icon_urls_for_tags(support_tag)    
        file_path = f'{mkdocs_root}/{docs_dir}/Categories/{support_tag}.md'
        category_template_file_name=f"./{mkdocs_root}/templates/category-template.j2"
        category_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
        category_jinja_template = category_jinja_env.get_template(category_template_file_name)
        category_content = category_jinja_template.render(
            category_tag=support_tag, 
            icon_url=icon_url
        )
        with open(file_path, 'w') as md_file:
            md_file.write(category_content)

    # for collection in data.get('codecollections', []):
    #     print(f"Indexing and genenerating content for {collection['name']}...")
    #     generate_codebundle_content(**collection)

    
    # # Generate stats and home page
    generate_index(all_support_tags_freq, all_codecollection_stats, codecollections_yaml=data)
    update_footer()

if __name__ == "__main__":
    main()