# WildMaps-processing

## Setting up

### What you'll need

* You need internet connection for both setting up and using the code.
* You’ll use the terminal (command line) to enter commands.
* It’s been built and tested on Mac. There’s a good chance it will run on other Unix systems (such as Linux) and a small chance it will run on Windows.
* Sensitive password files are not bundled in the project and you’ll have to get them from somebody who already has them (e.g. Harry or Chrishen).
* You will need to use the `git` command (discussed below).
* The land-use and protected area files are large (as they are global datasets), but necessary for the processing. Therefore you’ll need about 10 GB of disk space available.

### Set up Amazon Web Services (AWS) credentials

All the used by the WildMaps website are stored on the Simple Storage Service (S3) provided by Amazon Web Services (AWS). If (for some reason) you need to log in the [AWS website](console.aws.amazon.com) (‘console’), the account is `wildmaps3857@gmail.com`. Harry and Chrishen have the login password (as well as the password for gmail.com). However, the code uses a credentials file to simplify the login process.


The credential file is stored in a specific folder on your computer. Create this folder (this command is safe: if the folder already exists, nothing will happen):

```
mkdir -p ~/.aws
```

Note that if you see a dot (`.`) at the start of the directory or file name, as we see here, it means the file or folder is ‘hidden’: by default it won’t show up in a normal file browser, and it is ignored by many softwares.

Next, create the credentials file (this command is safe, it won’t overwrite the file if it already exists):

```
[ ! -f ~/.aws/credentials ] && touch ~/.aws/credentials
```

Open the credentials file with your favourite text editor and add the credentials at the end. They look like this (but get the real ones from Harry or Chrishen):

```
[WildMapsMaintainer]                                                            
aws_access_key_id = ABCDEDFGHIJK                                        
aws_secret_access_key = aBcDeF1234hLasdfJ
```

Now the code will know what password to use when interacting with AWS S3, specifically as the user `WildMapsMaintainer`, which is defined within our root account.

### Getting the code

Git is a software which manages code projects. On your command line, check you have git:

```
git --version
```

If you don’t have git, this command might trigger it to be installed automatically. Otherwise, look for instructions to install git on your system.

Once you have git: navigate to the parent folder, within which the project folder will sit, for example:

```
cd /Users/Documents/work/
```

Then use git to retrieve the code from GitHub:

```
git clone https://github.com/hkuril/WildMaps-processing.git
```

This will download all the files to (for example):

```
/Users/Documents/work/WildMaps-processing
```

It also sets up git for this folder, in case you ever want to share updates you’ve made to the code. You should go into the project folder:

```
cd WildMaps-processing
```

Use the `ls` command to check the contents look correct, it should be something like this

```
analyse_rasters
data_inputs
data_outputs
deploy_website.py
environment.yml
history-env.yml
interact_with_aws
make_and_upload_tiles
prep_reference_datasets
process_SDM_rasters.py
README.md
tools_only_used_during_development
utilities
website_dist
```
Note that some of the folders are empty by default, for example `data_inputs/raster` and `data_outputs`.


### Setting up conda environment

*Conda* is used to manage python packages. Install the minimal version (*miniconda*) by following the instructions here [here](https://www.anaconda.com/docs/getting-started/miniconda/install#macos).

Once that is done, run this command within the project directory:

```
conda env create -f environment.yml
```

This creates a specific Python environment called `WildMaps-processing` for running the code. It can take quite a long time (5–30 minutes).

Once the environment is created, it is saved on your system permanently. You have to activate the environment at the start of your session, like so:

```
conda activate WildMaps-processing
```
This should add some text to the start of your command prompt, something like this:

```
(WildMaps-processing) $ <-- could also be %
```

Congratulations, you can now run the code! But... the first commands to run are even more set-up commands.

** export pythonpath **

### Retrieve the large input files

A few of the files used in the processing are large and it is not smart to store them on GitHub. Instead they are stored on S3. Retrieve them using this command:

```
python3 interact_with_aws/get_large_input_files.py
```

It should print something like:

### Retrieve the latest version of the dataset catalog

Run this command:

```
python3 interact_with_aws/get_catalog_file.py
```
It should print something like:

```
INFO: Found credentials in shared credentials file: ~/.aws/credentials
INFO: Downloading s3://wildcru-wildmaps/data_inputs/catalogs/dataset_catalog.csv to data_inputs/catalogs/dataset_catalog.csv
INFO: Download complete.
```

## How to add a dataset to the website

The short answer is: to add a dataset to the website, you just need to add a new row to the dataset catalog (a CSV text file), put your input TIFF in the right place, and re-run the script. More details are below.

### Getting the input TIFF in the right place

Species distribution model (SDM) TIFF files must be copied into the project directory, specifically in

```
data_inputs/raster/SDM
```

they should have a sub-folder to group (by study). For example, here is one:

```
data_inputs/raster/SDM/burns_2025/borneo_asian_elephant_sdm_2021.tif
```

The TIFF file should be masked to the appropriate region (if you open up in QGIS, the masked areas should be transparent).

### The catalog file

The processing is controlled by a catalog file, whose location is:

```
https://wildcru-wildmaps.s3.eu-west-2.amazonaws.com/data_outputs/catalogs/dataset_catalog.csv
```

The file is a text file in CSV (comma-separated value) format, with headers and rows like this:

```csv
folder,input_file_name,common_name,region,subregion,source_link,source_text,band,scale_factor,overwrite,ignore
burns_2025,sumatra_yellow_throated_marten_sdm_2021.tif,yellow-throated marten,South East Asia,Sumatra,https://doi.org/10.3389/frsen.2025.1563490,Burns et al. (2025),1,10000,no,yes
chrishen,glm_pangosnewroads_seed333_1_1.tif,Sunda pangolin,South East Asia,Borneo,none,Gomez et al. (in prep.),1,1,no,yes
guilherme,HSM_jaguar_females_nodata_clean.tif,jaguar,Central America;South America,none,none,Alvarenga et al. (in prep.),1,1,no,yes
... and so on ...
```

When you start processing, the script will download the catalog file. It will also look for a local version of the catalog file:

```
./data_inputs/catalogs/dataset_catalog.csv
```

The script will merge the local and remote versions and synchronise them (so both versions will get updated). If there are any duplicate rows between the local and remote version (meaning the same `folder`, `common_name`, `region` and `subregion`) then the metadata from the local version is used. The script will then process every dataset in the catalog—but it it will skip any datasets that have already been processed, and those which have `ignore` set to `yes`.

### Rules for updating the catalog file 

Be careful to avoid leading and trailing spaces. Follow these rules for each column:

#### Columns `folder` and `input_file_name`

These relate to the file path, for example for this path:

```
data_inputs/raster/SDM/burns_2025/borneo_asian_elephant_sdm_2021.tif
```

then `folder` should be `burns_2025`, and `input_file_name` should be `borneo_asian_elephant_sdm_2021.tif`.

#### Column `common_name`

The common name of the species, for example `Asian elephant`.  If you are adding a new species (not already found in the catalog), you **must** add a new row to

`data_inputs/dictionaries/species_dictionary.csv`

and the `common_name` must match exactly. If you add a new species, and it has a new ‘superspecies’, you **must** also update 

`data_inputs/dictionaries/superspecies_dictionary.csv`

and the `superspecies` must match exactly.

#### Column `region`

The geographical region or regions of the dataset, based on the UN georegions scheme, such as `Southeast Asia`. For multiple regions, use a **semicolon** separator with no spaces, such as `Central America;South America`, in any order. Each value **must** match one of the entries in

```
data_inputs/dictionaries/region_dictionary.csv
```

#### Column `subregion`

A single subregion, such as `Borneo`. Your subregion must match one of the entries in

```
data_inputs/dictionaries/subregion_dictionary.csv
```

or you can add a new entry. To find the bounding box parameters, you can use this website: [](https://boundingbox.klokantech.com/) and select `CSV` to see the coordinates—just make sure to get the four values in the right order!

If your raster is large, then don’t specify `subregion`, just put `none`.

#### Columns `source_link` and `source_text`

These specify the information that will be provided to the user about the source of the data. For example, `source_link` could be the URL of a published paper:

```
https://doi.org/10.3389/frsen.2025.1563430
```

and `source_text` could be `Burns et al. (2025)`. If you’re not sure of either, put `none`.

#### Column `download_link`

The user will be provided with this link to download the data. It’s best to the data repository page (instead of the file download itself), so they can get context for their download. For example:

```
https://zenodo.org/records/15231415
```

#### Column `band`

For multi-band rasters, this specifies which band contains the SDM which you want to analyse and show on the website. For single-band rasters, just put 1. The band index starts from 1, not 0.

#### Column `scale_factor`

This column is ignored and will be deleted in a future release. Just put 1.

#### Column `overwrite`

This column is ignored for now but might be used in a future release. Just put `no`.

#### Column `ignore`

If this column is set to `yes`, processing is skipped completely for this dataset.

#### Other notes on updated the catalog file

* You **must** save the file as a `CSV UTF-8 (Comma-delimited)`. This should happen by default based on the `.csv` file extension.
* Updates: `species_dictionary.csv`, `superspecies_dictionary.csv`, `subregion_dictionary.csv`.
```
python3 interact_with_aws/send_updated_input_files.py
```

### Once you have updated the catalog file

If you edited or added rows to any of the dictionary files, run this command to make sure they’re also updated on S3:

```
python3 interact_with_aws/send_updated_input_files.py
```

(If you’re not sure if you updated the input files, you can run this script anyway.)

### Processing the rasters

Finally, you can run the script like this:

```
python3 process_SDM_rasters.py
```

It will loop through all the datasets in the catalog. It will perform two main steps:

 * Analysis of the SDM (binning by suitability-PAs and by suitability–land use), including for various sub regions (national and sub-national). The results are saved as JSON files in `data_outputs/raster_analysis`.
 * Generation of tiles for web map visualisation. The results are saved in `data_outputs/raster_tiles/SDM`.