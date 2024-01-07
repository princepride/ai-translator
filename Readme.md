## AI_Translator Instructions

### Setup

**Requirements:** In order to set up the project locally, you need to first satisfy the following requirements:

1. Docker installed on your computer. Here is the installation guide for docker [Install Docker Engine | Docker Documentaion](https://docs.docker.com/engine/install/)
2. Docker-compose install on your computer. Here is the installation guide for docker-compose [Install Docker Compose | Docker Documentation](https://docs.docker.com/compose/install/)



### Run

1. **Clone the Res:** 

   Clone this res to your local machine. Use the command:

   ```git clone https://github.com/princepride/ai-translator.git```

2. **Navigate to the Dockerfile Directory:**

​	Change directory to where the Dockerfile is located:

​	```cd [path to the Dockerfile directory]```

3. **Build the Docker Image:**

   Build your Docker image using:

   ```docker build -t [your-image-name].```

   **note:** don't forget "." in the command

4. **Run the Docker Container:**

   Run it using:

   ```docker run -it [your-image-name]```

5. **Launch:**

   In the terminal of your python project platform such as: pycharm, Vscode...

   Enjoy the AI-Translator using the command:

   ```launch.py```



***Tips*** Ensure to replace `[your-image-name]` and `[path to the Dockerfile directory]` with actual image name and directory path.