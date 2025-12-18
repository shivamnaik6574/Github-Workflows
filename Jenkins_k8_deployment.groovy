pipeline {
    agent any
    environment {
        // Define base Docker image name
        DOCKER_IMAGE_BASE = 'your-docker-repo/your-app'
        DEV_IMAGE_TAG = 'dev-latest'
        STAGE_IMAGE_TAG = 'stage-latest'
        PROD_IMAGE_TAG = 'prod-latest'
        QA_IMAGE_TAG = 'qa-latest'

        DEV_KUBECONFIG = '/path/to/dev-kubeconfig'
        STAGE_KUBECONFIG = '/path/to/stage-kubeconfig'
        PROD_KUBECONFIG = '/path/to/prod-kubeconfig'
        QA_KUBECONFIG = '/path/to/qa-kubeconfig'
    }
    stages {
        stage('Clone Repository') {
            steps {
                git branch: "${env.GIT_BRANCH}", url: 'https://your-repo-url.git'
            }
        }
        stage('Build Docker Image') {
            when {
                branch 'dev' // Only build images for the dev branch
            }
            steps {
                script {
                    docker.build("${DOCKER_IMAGE_BASE}:${DEV_IMAGE_TAG}")
                }
            }
        }
        stage('Push Docker Image') {
            when {
                branch 'dev' // Push new image only for the dev branch
            }
            steps {
                script {
                    docker.withRegistry('https://your-docker-registry', 'docker-credentials-id') {
                        docker.image("${DOCKER_IMAGE_BASE}:${DEV_IMAGE_TAG}").push()
                    }
                }
            }
        }
        stage('Deploy to Kubernetes') {
            steps {
                script {
                    def kubeconfig = ''
                    def imageTag = ''

                    if (env.GIT_BRANCH == 'dev') {
                        kubeconfig = DEV_KUBECONFIG
                        imageTag = DEV_IMAGE_TAG
                    } else if (env.GIT_BRANCH == 'stage') {
                        kubeconfig = STAGE_KUBECONFIG
                        imageTag = STAGE_IMAGE_TAG
                    } else if (env.GIT_BRANCH == 'prod') {
                        kubeconfig = PROD_KUBECONFIG
                        imageTag = PROD_IMAGE_TAG
                    } else if (env.GIT_BRANCH == 'qa') {
                        kubeconfig = QA_KUBECONFIG
                        imageTag = QA_IMAGE_TAG
                    } else {
                        error("Unsupported branch: ${env.GIT_BRANCH}")
                    }

                    sh """
                    kubectl --kubeconfig=${kubeconfig} set image deployment/your-deployment-name your-container-name=${DOCKER_IMAGE_BASE}:${imageTag}
                    """
                }
            }
        }
    }
    post {
        success {
            echo 'Deployment Successful!'
        }
        failure {
            echo 'Deployment Failed.'
        }
    }
}
