def pipelineFor(String jobName, String target, String chartKind, String valuesFile, String workloadName, String repository) {
  pipeline {
    agent none
    options {
      skipDefaultCheckout(true)
    }
    stages {
      stage('test') {
        agent { label 'built-in' }
        steps {
          checkout scm
          sh 'git diff --name-status "${EDAI2_VERIFIED_BASE:?}...${GIT_COMMIT:?}" > changed-paths.tsv'
          sh 'python3 ci/jenkins/scripts/select_jobs.py --changes-file changed-paths.tsv ${EDAI2_FORCE_ALL:+--force-all} > selected-jobs.json'
          sh 'uv run pytest tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py -q'
          stash name: "source-${jobName}", includes: '**', useDefaultExcludes: false
        }
      }
      stage('build') {
        agent {
          kubernetes {
            yamlFile 'ci/jenkins/buildkit-pod.yaml'
            defaultContainer 'buildkit'
          }
        }
        steps {
          script {
            lock(resource: 'edai2-buildkit-slot', quantity: 1) {
              unstash "source-${jobName}"
              sh "mkdir -p artifacts && buildctl-daemonless.sh build --frontend dockerfile.v0 --local context=. --local dockerfile=containers/edai2 --opt filename=Dockerfile --opt target=${target} --output type=docker,dest=artifacts/${jobName}.tar"
              stash name: "archive-${jobName}", includes: "artifacts/${jobName}.tar"
            }
          }
        }
      }
      stage('scan') {
        agent { label 'built-in' }
        steps {
          unstash "archive-${jobName}"
          sh "ci/jenkins/scripts/release.sh scan_archive ${jobName}"
          stash name: "reports-${jobName}", includes: "reports/${jobName}-*"
        }
      }
      stage('push_sha') {
        agent { label 'built-in' }
        steps {
          unstash "archive-${jobName}"
          unstash "reports-${jobName}"
          sh "ci/jenkins/scripts/release.sh push_archive ${jobName}"
          stash name: "reports-${jobName}", includes: "reports/${jobName}-*"
        }
      }
      stage('helm_atomic') {
        agent { label 'built-in' }
        steps {
          unstash "reports-${jobName}"
          sh "ci/jenkins/scripts/release.sh helm_atomic ${jobName} ${chartKind} ${valuesFile} ${workloadName} ${repository}"
        }
      }
      stage('smoke_eval') {
        agent { label 'built-in' }
        steps {
          unstash "reports-${jobName}"
          sh "ci/jenkins/scripts/release.sh smoke_eval ${jobName}"
        }
      }
      stage('rollback_proof') {
        agent { label 'built-in' }
        steps {
          unstash "reports-${jobName}"
          sh "ci/jenkins/scripts/release.sh rollback_proof ${jobName}"
        }
      }
    }
    post { always { archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: false } }
  }
}

return this
