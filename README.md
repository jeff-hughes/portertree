# Porter family tree

This is the code repository for the Porter family history, available at [porterfamilytree.ca](http://porterfamilytree.ca).

If you would like to suggest updates to the family tree itself (e.g., births, deaths, marriages), please use the [report page](http://porterfamilytree.ca/report) on the website itself. Suggestions for code improvements can be raised by opening an issue or pull request on the [Github page](https://github.com/jeff-hughes/portertree).

## Deploying the app

This website is licensed with a GPLv3 license; so, you are free to use and modify the code for your own purposes provided that your use/modifications are also distributed under the GPLv3 license and the source made available. See the LICENSE file for the full license.

The app is contained in Docker containers for ease of dependency management, so the primary dependency is Docker itself. [Follow the instructions](https://docs.docker.com/get-docker/) to install Docker for your OS, and also be sure to [install Docker Compose](https://docs.docker.com/compose/install/) as well if it does not come with your Docker installation. (The latter is not a hard requirement, but makes it simpler to set up the containers.)

Clone the git repo to your local system. You'll need to copy `.env.template` to create a `.env` file, and fill in values for the variables in it. Then, in a terminal, navigate to the project directory, and run:

```bash
docker-compose -f compose.common.yml -f compose.dev.yml up -d --build
```

This should build the images, set up the network and volumes, and start the containers. On subsequent runs, the `--build` flag is not necessary. Give it a minute or so, and then the app should be available on http://localhost:8080.

To stop the app, run:

```bash
docker-compose -f compose.common.yml -f compose.dev.yml down
```

Follow a similar process if you want to set up the app for production (rather than development), substituting `compose.dev.yml` for `compose.prod.yml`.

## Modifying the app

If you want to take this and use it for your own family tree, the main change will be to substitute the .csv files in the `db/` directory. The `people.csv` file is the full list of all people in the tree, with `id` being the primary key for referencing from the other tables. `marriages.csv` refers to two `id` values, along with some data about the marriage itself. `children.csv` has one row per parent-child relationship. (Of course, in most cases, there will be two rows per child, but this approach would also handle cases of adoption. This table layout may still not be the best approach, though, to be honest.) As long as you can set up the data for your own family tree in a similar way, you should be able to replace these .csv files and be all set.

The other change to make will be to look through the `app/app/templates/` directory and adjust the HTML templates to suit you. Note in particular the "extended" templates that provide some additional long-form content for some of the early members in the family tree. These special cases are handled semi-manually, with a list of person IDs in the `EXTENDED_NOTES` list near the top of `app/app/main.py`.

For any more significant changes, you may also need to adjust the Linux/Python dependencies, which are in `app/Dockerfile`.

I make no guarantees about how well this app will suit your own family tree, but if you need any help making it work, feel free to open a Github issue/discussion and I'm happy to try to help you out.