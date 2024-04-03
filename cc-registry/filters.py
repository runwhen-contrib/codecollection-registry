import os
import markdown
import yaml

def extract_front_matter(md_content):
    """
    Extracts the YAML front matter from the given markdown content.
    """
    lines = md_content.split('\n')
    if lines[0] == '---':
        end_fm_index = lines[1:].index('---') + 1
        fm_content = '\n'.join(lines[1:end_fm_index])
        try:
            return yaml.safe_load(fm_content), '\n'.join(lines[end_fm_index+1:])
        except yaml.YAMLError as e:
            print(f"Error parsing YAML: {e}")
    return {}, md_content  # Return empty dict if no front matter found

def include_content_with_tag(config, tag):
    content = ""
    for root, dirs, files in os.walk(config['docs_dir']):
        for md_file in files:
            if md_file.endswith(".md"):
                with open(os.path.join(root, md_file), 'r') as file:
                    md_content = file.read()
                    front_matter, body = extract_front_matter(md_content)
                    # Check if 'tags' key exists and the specified tag is in the list
                    if front_matter.get('tags') and tag in front_matter['tags']:
                        html = markdown.markdown(body)
                        content += html
    return content

def define_env(env):
    """
    Called by the Macros plugin to define custom functions and variables.
    """
    @env.macro
    def include_tagged_content(tag):
        return include_content_with_tag(env.conf, tag)
