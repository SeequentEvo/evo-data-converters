# Setup for the Evo DUF converter automation script

The Evo DUF converter automation script is designed to work with no human interaction. Therefore, before getting started you must provide several parameters which are saved into an environment file called `.env`.

This document explains how to obtain or create these parameters.

## Required parameters

Once you have completed the steps below, return to the main README file to complete setup of the script.

- [Evo instance ID and Evo hub URL](#how-to-find-your-evo-instance-id-and-evo-hub-url)
- [Evo workspace ID](#how-to-find-your-evo-workspace-id)
- [Credentials for an Evo service app](#how-to-register-an-evo-service-app)
- [EPSG code](#how-to-find-an-epsg-code)

## How to find your Evo instance ID and Evo hub URL

a. Visit the [Evo Discovery](https://developer.seequent.com/docs/guides/getting-started/discovery) page of the Seequent Developer Portal.

b. In the top-right corner, click the **Sign in** button and sign in with your Evo credentials.

<img src="img/dev-portal-sign-in.png" alt="Select My Apps" width="350" />

c. Once you've signed in you should see the **Run request** button in the **Try it out!** section. Click the button to run the request.

<img src="img/dev-portal-discovery1.png" alt="Select My Apps" width="500" />

d. From the API response copy the Evo hub URL from the `hubs` section and copy the instance ID from the `organizations` section. NOTE: Evo is in the process of moving from being *organisation*-based to being *instance*-based, which is why these two terms are often used interchangeably. 

<img src="img/discovery-response.png" alt="Select My Apps" width="500" />

## How to find your Evo workspace ID

When converting a DUF file to Evo geoscience objects, you must provide the ID of the Evo workspace that will store these objects.

The instructions below represent one of several ways to find the workspace ID.

a. Open your web browser and sign in to the [Evo portal](https://evo.seequent.com/).

b. Open the **Workspaces** tab and either create a new workspace or click to open an existing workspace.

<img src="img/create-workspace.png" alt="Select My Apps" width="700" />

c. In the URL bar at the top of your web browser, copy the ID that sits between your Evo hub code (*evo-demo* in this example) and the work "overview".

<img src="img/workspace-id.png" alt="Select My Apps" width="900" />

## How to register an Evo service app

Register your Evo service application in the [Bentley Developer Portal](https://developer.bentley.com/my-apps) to get your client credentials. If a member of your team has already registered an app, contact them and ask for the client credentials. For in-depth instructions, follow this [guide](https://developer.seequent.com/docs/guides/getting-started/apps-and-tokens) on the Seequent Developer Portal.

a. In a new browser tab or window, visit [https://developer.bentley.com/](https://developer.bentley.com/) and sign in.

b. Click your profile in the top-right corner and select **My Apps**. You may need to agree to Bentley developer terms before proceeding.

<img src="img/profile-menu-apps.png" alt="Select My Apps" width="250" />

c. Click the dropdown arrow on the **Register New** button and choose **Register new app for Seequent Evo**.

<img src="img/register-new.png" alt="Register new app" width="300" />

d. Enter an application name and select the **Service** application type.

HINT: Ensure you can see scopes listed in the *Scopes* section that mention `evo`, eg. `evo.discovery` or `evo.object`. If you only see the scope `itwin-platform` you will need to go back to step 1 in this list.

<img src="img/app-name-service.png" alt="Enter app name" width="700" />

e. Click **Register**.

<img src="img/app-register.png" alt="Click register" width="250" />

f. The next screen displays the unique **Client ID** and **Client secret** of your application. You must save a copy of each before closing this window - this is the only time you will be shown the secret.

<img src="img/app-copy-creds.png" alt="Copy client ID" width="700" />

g. After closing the window with the unique credentials you'll see the page for your new app. At the top of the screen is the email address that is associated with the app. Click the button to copy it and save it alongside the other credentials.

<img src="img/app-copy-email.png" alt="Copy client ID" width="700" />

### How to find an EPSG code

To take advantage of Evo spatial search you can provide a coordinate reference system (CRS) for your geoscience objects.

To find a valid EPSG code to apply to your objects:

a. Visit [EPSG.io](https://epsg.io/) and use the search box to find codes that are relevant to you.

<img src="img/epsg1.png" alt="Copy client ID" width="500" />

b. Browse the results and find a listing that includes an EPSG code.

<img src="img/epsg2.png" alt="Copy client ID" width="500" />

## 📖 Additional resources

- [Seequent Developer Portal](https://developer.seequent.com/)
- [Seequent Community](https://community.seequent.com/group/19-evo)
- [Evo Python SDK README](../README.md)

## 🆘 Getting help

If you encounter issues:
1. Check that you've completed the authentication setup.
2. Verify your Python version (3.10+).
3. Ensure all requirements are installed.
4. Visit the [Seequent Community](https://community.seequent.com/group/19-evo) for support.
5. Check the [GitHub issues](https://github.com/SeequentEvo/evo-python-sdk/issues) for known problems.

Happy coding with Evo! 🎉

