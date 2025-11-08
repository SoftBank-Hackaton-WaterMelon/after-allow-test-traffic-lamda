AfterAllowTestTraffic Lambda
=============================

## 개요

- AWS CodeDeploy의 `AfterAllowTestTraffic` 훅에서 호출되는 서버리스 함수입니다.
- 새 배포가 테스트 트래픽을 허용한 직후, 배포 메타데이터를 Amazon DynamoDB에 저장하고 Slack으로 테스트 준비 완료 알림을 전송합니다.
- 배포 승인·테스트 담당자가 신속하게 테스트 환경을 확인하고 승인 명령을 실행할 수 있도록 돕습니다.

## 동작 흐름

1. 함수가 호출되면 CodeDeploy 이벤트 페이로드를 로깅합니다.
2. 필수 환경 변수(`SLACK_WEBHOOK_URL`, `TEST_URL`, `DYNAMODB_TABLE_NAME`)를 확인합니다.
3. 이벤트에서 `DeploymentId`, `LifecycleEventHookExecutionId`를 추출합니다.
4. DynamoDB 테이블에 배포 ID와 훅 실행 ID를 저장합니다.
5. Slack 수신 웹훅으로 배포 정보를 포함한 메시지를 전송합니다.
6. 모든 단계가 성공하면 HTTP 200 응답을 반환하고, 실패 시 예외를 발생시켜 CodeDeploy에 오류를 전달합니다.

## 코드 구조

```
lamda.py
├─ lambda_handler(event, context)
│  ├─ 환경 변수 로딩
│  ├─ CodeDeploy 이벤트 파싱
│  ├─ DynamoDB put_item 수행
│  └─ Slack 웹훅 호출
```

## 필요 리소스 및 권한

- **AWS Lambda**: Python 3.x 런타임.
- **Amazon DynamoDB**: 배포 메타데이터(`deployment_id`, `hook_execution_id`) 저장용 테이블.
- **Slack Incoming Webhook**: 테스트 환경 준비 알림을 전송.
- **IAM 권한**:
  - `dynamodb:PutItem` (대상 테이블)
  - `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` (CloudWatch Logs)
  - (선택) `codedeploy:PutLifecycleEventHookExecutionStatus` 등 후속 훅 상태 업데이트가 필요한 경우 추가.

## 환경 변수

| 이름 | 설명 | 예시 |
| --- | --- | --- |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | `https://hooks.slack.com/services/...` |
| `TEST_URL` | 테스트용 애플리케이션 엔드포인트, Slack 메시지에 하이퍼링크로 제공 | `https://green.example.com/health` |
| `DYNAMODB_TABLE_NAME` | 배포 메타데이터를 저장할 테이블 이름 | `after-allow-test-traffic` |

## 예시 이벤트(JSON)

```json
{
  "DeploymentId": "d-ABCXYZ123",
  "LifecycleEventHookExecutionId": "hook-456"
}
```

CodeDeploy가 보내는 실제 이벤트는 더 많은 필드를 포함할 수 있으나, 본 함수는 위 두 필드만 사용합니다.

## Slack 메시지 형식

- 헤더: ✅ 이모지와 함께 “ECS 배포: 테스트 대기 중” 제목 표시
- 메시지 블록:
  - 배포 ID 및 테스트 URL 표기
  - 테스트 완료 후 실행해야 할 승인 명령 안내
  - 배포 완료 GIF 이미지 표시 (GitHub 호스팅)

## 오류 처리

- 환경 변수 누락, 이벤트 키 누락, DynamoDB 저장 실패, Slack HTTP 오류마다 개별적으로 로깅 후 예외를 발생시킵니다.
- Lambda 함수가 예외를 던지면 CodeDeploy는 해당 훅을 실패로 간주하므로, 문제가 해결된 뒤 재시도가 필요합니다.

## 로컬/사전 점검 방법

1. `python -m venv .venv && source .venv/bin/activate` (Windows PowerShell은 `.\.venv\Scripts\Activate.ps1`)
2. `pip install boto3`
3. 아래처럼 가짜 환경 변수와 이벤트 입력으로 핸들러를 호출해 Slack 요청이 만들어지는지 확인합니다.

```python
import os
from lamda import lambda_handler

os.environ["SLACK_WEBHOOK_URL"] = "https://example.com/mock"
os.environ["TEST_URL"] = "https://green.example.com"
os.environ["DYNAMODB_TABLE_NAME"] = "after-allow-test-traffic"

event = {
    "DeploymentId": "d-LOCALTEST",
    "LifecycleEventHookExecutionId": "hook-local"
}

lambda_handler(event, None)
```

> 참고: 실제 Slack 호출 및 DynamoDB 접근을 막으려면 `urllib.request.urlopen`, `boto3.resource` 등을 `unittest.mock`으로 패치하세요.

## 배포 팁

- CodeDeploy 애플리케이션/배포 그룹의 `AfterAllowTestTraffic` 훅에 이 Lambda를 연결합니다.
- 배포 파이프라인(IaC, CD 파이프라인 등)에서 환경 변수를 설정하고, Lambda의 IAM 역할에 DynamoDB, CloudWatch Logs 권한을 부여합니다.
- 배포 전 Slack 웹훅 URL이 외부에 노출되지 않도록 AWS Systems Manager Parameter Store 또는 AWS Secrets Manager 활용을 권장합니다.

## 모니터링

- CloudWatch Logs에서 `lambda_handler` 로그를 확인하여 Slack 응답, DynamoDB 저장 결과, 오류 메시지를 추적할 수 있습니다.
- Slack 채널에서 알림이 도착했는지 확인하여 테스트 환경 준비 완료 플로우를 검증합니다.

