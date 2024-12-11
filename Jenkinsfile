def GIT_CREDENTIALS = 'bitbucket-password-credentials'
def AGENT_LABEL = 'ec2-t2-micro'
def DEFAULT_AWS_REGION = 'us-east-1'
def MAIN_AWS_CREDENTIALS_NAME = 'main-aws-credentials'
def ACCOUNT_NAME = 'Matter Software Ltd'

properties([
    buildDiscarder(logRotator(artifactNumToKeepStr: '10', numToKeepStr: '10'))
])

pipeline {
    agent {
        label AGENT_LABEL
    }

    options {
        skipStagesAfterUnstable()
        skipDefaultCheckout(true)
        ansiColor('xterm')
    }

    parameters {
        string(defaultValue: DEFAULT_AWS_REGION, description: 'AWS Region', name: 'AWS_REGION')
    }

    environment {
        IMAGE_TAG = 'latest'
        IMAGE_REPO_REGISTRY = 'public.ecr.aws/e0w7o6a1/e57-converter-repository'
        GIT_REPOSITORY_URL = 'https://treedis_automation@bitbucket.org/treedis/convert-e57.git'
        IMAGE_REPO_NAME = 'e57-converter-repository'
    }

    stages {
        stage('Prebuild') {
            steps {
                withAWS(credentials: MAIN_AWS_CREDENTIALS_NAME) {
                    script {
                        def accounts = listAWSAccounts()
                        def account = accounts.find { it.name == ACCOUNT_NAME }
                        if (account) {
                            env.AWS_ACCOUNT_ID = account.id
                        } else {
                            error "AWS Account 'Matter Software Ltd' not found."
                        }
                    }
                }
            }
        }

        stage('Checkout Source') {
            steps {
                timeout(time: 1, unit: 'MINUTES') {
                    script {
                        checkout([
                            $class: 'GitSCM',
                            branches: [[name: '*/master']],
                            userRemoteConfigs: [[
                                url: GIT_REPOSITORY_URL,
                                credentialsId: GIT_CREDENTIALS
                            ]]
                        ])
                    }
                }
            }
        }

        stage('Docker Build') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: GIT_CREDENTIALS,
                    usernameVariable: 'BITBUCKET_USERNAME',
                    passwordVariable: 'BITBUCKET_PASSWORD'
                )]) {
                    withAWS(credentials: MAIN_AWS_CREDENTIALS_NAME) {
                        sh '''
                            docker build -t $IMAGE_REPO_NAME:$IMAGE_TAG --no-cache .
                        '''
                    }
                }
            }
        }
        stage('Push to ECR') {
            steps {
                withAWS(credentials: MAIN_AWS_CREDENTIALS_NAME) {
                    sh '''
                        docker tag $IMAGE_REPO_NAME:$IMAGE_TAG $IMAGE_REPO_REGISTRY:$IMAGE_TAG
                        docker push $IMAGE_REPO_REGISTRY:$IMAGE_TAG
                        docker system prune -f
                    '''
                }
            }
        }
    }

    post {
        always {
            cleanWs(deleteDirs: true)
        }

        failure {
            script {
                def failureMessage = """
                Environment: ${params.AWS_REGION}
                Branch: ${env.GIT_BRANCH}
                Job ID: ${env.BUILD_ID}
                User: ${env.BUILD_USER_ID}
                Status: FAILURE
                Error description: ${env.BUILD_ERROR}
                <${env.RUN_DISPLAY_URL}|View Build Report>
                """
                slackSend(
                    color: 'danger',
                    message: failureMessage,
                    channel: "${env.SLACK_CHANNEL}"
                )
            }
        }
    }
}
