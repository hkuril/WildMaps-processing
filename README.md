# WildMaps-processing

## Setting up

### What you'll need

* You need internet connection for both setting up and using the code.
* You’ll use the terminal (command line) to enter commands.
* It’s been built and tested on Mac. There’s a good chance it will run on other Unix systems (such as Linux) and a small chance it will run on Windows.
* Sensitive password files are not bundled in the project and you’ll have to get them from somebody who already has them (e.g. Harry or Chrishen).
* You will need to use the `git` command (discussed below).

### Set up Amazon Web Service (AWS) credentials

The credentials are stored in a file in a specific folder on your computer. Create this folder (this command is safe: if the folder already exists, nothing will happen):


### Getting the code

Git is a software which manages code projects. On your command line, check you have git:

```
git --version
```

If you don’t have git, this command might trigger it to be installed automatically. Otherwise, look for instructions to install git on your system.

Once you have git,

Navigate to the parent folder, within which the project folder will sit, for example:

```
cd /Users/Documents/work/
```




### Setting up conda environment

*Conda* is used to manage python packages. Install the minimal version (*miniconda*) by following the instructions here [here](https://www.anaconda.com/docs/getting-started/miniconda/install#macos).

Once that is done

```
conda env create -f environment.yml
```

### Setting up AWS credentials
In 

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
The short answer is: to add a dataset to the website, you just need to add a new row to the dataset catalog (a CSV text file), and re-run the script. More details are below

### The catalog file

The processing is controlled by a catalog file:
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

The script will merge the local and remote versions and synchronise them (so both versions will get updated). If there are any duplicate rows between the local and remote version (meaning the same `folder`, `common_name`, `region` and `subregion`) then the metadata from the local version is used. The script will then process every dataset in the catalog (but it will skip any datasets that have already been processed).

### Rules for updating the catalog file 

I script to process a new raster and add it to the website. Be careful to follow these rules:

* Note that `region` can be a list separated by semicolons like `Central America;South America`
... more notes
* You **must** save the file as a `CSV UTF-8 (Comma-delimited)`. This should happen by default based on the `.csv` file extension.
* Updates: `species_dictionary.csv`, `superspecies_dictionary.csv`, `subregion_dictionary.csv`.
```
python3 interact_with_aws/send_updated_input_files.py
```

### Once you have updated the catalog file

Run the script like this:

```sh
python3 process_SDM_rasters.py
```

## Other notes
* If you have set up the AWS credentials file as described above, and also installed the AWS command-line tools, you can send a file to AWS like this:
```
aws s3 cp /local/path/to/your/foo.txt s3://wildcru-wildmaps/remote/path/to/your/bar.txt --profile WildMapsMaintainer
```

* Similarly, you can delete a directory like this:
```
aws s3 rm s3://wildcru-wildmaps/data_outputs/remote/path/ --recursive --profile WildMapsMaintainer
```

```
python3 interact_with_aws/change_policies.py bucket_policy data_inputs/managing_s3/bucket_policy_restricted.json
```
```
python3 interact_with_aws/change_policies.py cors data_inputs/managing_s3/cors_policy_unrestricted.json
```