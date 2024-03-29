import json
import ruamel.yaml as yaml
import requests
import urllib.parse
import os

def get_urls(user=None):
    pipeline_urls = []
    if 'PIPELINES_URL' in os.environ:
        pipeline_urls = [os.getenv('PIPELINES_URL')]

    if user is not None:
        from app.plugins import get_current_plugin
        ds = get_current_plugin().get_user_data_store(user)
        urls = ds.get_string('pipelines_url', "")
        if urls:
            pipeline_urls += urls.split(',')

    return pipeline_urls

def get_all(user):
    #Get all pipelines with the launch url, requires user
    pipelines = get_json(user)
    for p in pipelines:
        p["url"] = get_fullurl(p, user.email, encode_again=False)
    return pipelines

def get_json(user=None):
    pipeline_urls = get_urls(user)

    pipelines = []
    for url in pipeline_urls:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            try:
                pipeline = yaml.safe_load(response.text)
                pl = pipeline['pipelines']
                #First entry = defaults, subsequent = custom
                custom = (len(pipelines) > 0)
                #Set the custom flag
                for p in pl:
                    p['custom'] = custom
                pipelines.extend(pl)
                #if not custom:
                #    #Divider - null pipeline
                #    pipelines.extend({"name": "", "tag": "", "description": "", "maintainer": "", "source": "", "image": "", "entrypoint": "", "icon": "", "inputs": "", "custom": false})
            except (Exception) as e:
                from app.plugins import logger
                logger.error("Error parsing yaml:" + str(e))
                pass

    return pipelines

def get_nexturl(pipeline):
    #Construct the next= url
    tag = pipeline["tag"]
    image = pipeline["image"]
    branch = ""
    requirements = ""
    # - Source repository and repo checkout dest dir
    if ':' in pipeline["source"]:
        #Provided a full repo URL
        repo = pipeline["source"]
        target = tag #Use the tag as the dest dir
        # - Entrypoint path
        path = os.path.join(target, pipeline["entrypoint"])
        # - Requirements file (optional)
        if "requirements" in pipeline:
            requirements = "&requirements=" + pipeline["requirements"]
    else:
        repo = os.getenv('PIPELINE_REPO', "https://github.com/auscalabledronecloud/pipelines-jupyter")
        target = 'pipelines'
        # - Entrypoint path
        #(NOTE: can be confusing, but assumes entrypoint relative to source subdir)
        path = os.path.join("pipelines", pipeline["source"], pipeline["entrypoint"])
        # - Requirements file (optional)
        if "requirements" in pipeline:
            #Same with requirements, assumes relative to source subdir
            requirements = "&requirements=" + os.path.join(pipeline["source"], pipeline["requirements"])
    # - Branch (optional)
    if "branch" in pipeline:
        branch = "&branch=" + pipeline["branch"]
    #branch = "&branch=" + (pipeline["branch"] if "branch" in p else "main") #Seems to require branch

    #Encode urlpath, then re-encode entire next url
    #(NOTE: need to replace PROJECTS and TASKS with data in js)
    urlpath = urllib.parse.quote_plus(f'asdc/redirect?projects=PROJECTS&tasks=TASKS&path={path}')
    nexturl = urllib.parse.quote_plus(f"/user-redirect/{image}/git-pull?repo={repo}{branch}&targetpath={target}{requirements}&urlpath={urlpath}")
    return nexturl

def get_fullurl(pipeline, username, use_mounts=True, encode_again=True, image='base'):
    if pipeline is None:
        #Defaults to pulling the pipelines repo, but not opening any notebook
        pipeline = {'name': 'Default',
                    'tag': 'dev',
                    'source': 'dev',
                    'image': image,
                    'entrypoint': '',
                    }

    host = os.environ.get('WO_HOST')
    nexturl = ''
    nexturl = get_nexturl(pipeline)
    image = pipeline['image']
    mounts = ""
    if use_mounts:
        #If projects passed in to spawner, will be mounted
        mounts = "&projects=PROJECTS"
        #mounts = "&projects=PROJECTS&tasks=TASKS"
    fullurl = f'https://jupyter.{host}/hub/spawn/{username}/{image}?profile={image}{mounts}&next={nexturl}'
    #Fix for react, encode_again=True bug, it decodes the url when rendering so encode again to counter this
    if encode_again:
        fullurl = urllib.parse.quote_plus(fullurl)
    return fullurl

def get_baseurl():
    host = os.environ.get('WO_HOST')
    return f'https://jupyter.{host}/hub/home'
