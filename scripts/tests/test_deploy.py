"""Pruebas sin AWS: destino de credenciales, cuentas y despliegue no destructivo."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import MagicMock, patch
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cloud
import smoke
import source_matrix
from botocore.credentials import Credentials
from botocore.exceptions import ClientError


ACCOUNT = "123456789012"
SHA = "a" * 40


def error(code, message="Error simulado"):
    return ClientError({"Error": {"Code": code, "Message": message}}, "Prueba")


class AccountTests(TestCase):
    def test_invalid_region_never_requests_credentials(self):
        with patch.dict(os.environ, {"AWS_REGION": "eu-west-1"}), patch.object(cloud.boto3, "Session") as create:
            with self.assertRaises(ValueError):
                cloud.session()
            create.assert_not_called()

    def test_only_configured_account_and_learner_session_are_accepted(self):
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1", "FOODGO_AWS_ACCOUNT_ID": ACCOUNT}), patch.object(cloud.boto3, "Session") as create:
            sts = create.return_value.client.return_value
            sts.get_caller_identity.return_value = {"Account": ACCOUNT, "Arn": f"arn:aws:sts::{ACCOUNT}:assumed-role/voclabs/alumno"}
            self.assertEqual(ACCOUNT, cloud.session()[1])
            sts.get_caller_identity.return_value["Account"] = "999999999999"
            with self.assertRaises(ValueError):
                cloud.session()
            sts.get_caller_identity.return_value.update(Account=ACCOUNT, Arn=f"arn:aws:sts::{ACCOUNT}:assumed-role/LabRole/instancia")
            with self.assertRaises(ValueError):
                cloud.session()


class StackTests(TestCase):
    def test_access_denied_is_not_treated_as_missing_stack(self):
        client = MagicMock()
        client.describe_stacks.side_effect = error("AccessDenied")
        with self.assertRaises(ClientError):
            cloud.stack(client, cloud.CLUSTER)
        client.describe_stacks.side_effect = error("ValidationError", "Stack does not exist")
        self.assertIsNone(cloud.stack(client, cloud.CLUSTER))

    def test_first_creation_protects_manager_and_passwords_without_new_iam_role(self):
        client = MagicMock()
        with patch.object(cloud, "stack", return_value=None), patch.object(cloud, "outputs", return_value={}), TemporaryDirectory() as folder:
            path = Path(folder) / "template.yaml"
            path.write_text("Resources: {}", encoding="utf-8")
            cloud.deploy_template(client, cloud.CLUSTER, path, {"LinuxAmi": "ami-1234"})
        args = client.create_stack.call_args.kwargs
        protected = json.loads(args["StackPolicyBody"])["Statement"][1]
        self.assertIn("LogicalResourceId/SwarmManager", protected["Resource"])
        self.assertIn("LogicalResourceId/AppDatabasePassword", protected["Resource"])
        self.assertIn("Update:Replace", protected["Action"])
        self.assertNotIn("RoleARN", args)
        self.assertNotIn("Capabilities", args)
        self.assertEqual("ROLLBACK", args["OnFailure"])

    def test_no_changes_keeps_existing_stack(self):
        client = MagicMock()
        client.update_stack.side_effect = error("ValidationError", "No updates are to be performed.")
        with patch.object(cloud, "stack", return_value={"StackStatus": "UPDATE_COMPLETE"}), patch.object(cloud, "outputs", return_value={"vigente": "si"}), TemporaryDirectory() as folder:
            path = Path(folder) / "template.yaml"
            path.write_text("Resources: {}", encoding="utf-8")
            self.assertEqual({"vigente": "si"}, cloud.deploy_template(client, cloud.CLUSTER, path, {}))
        client.create_stack.assert_not_called()
        client.delete_stack.assert_not_called()


class SigningTests(TestCase):
    def setUp(self):
        self.session = MagicMock(region_name="us-east-1")
        self.session.get_credentials.return_value = Credentials("CLAVE_DE_PRUEBA", "SECRETO_DE_PRUEBA", "TOKEN_DE_PRUEBA")

    def test_credentials_cannot_be_signed_to_another_host_or_redirect(self):
        invalid = ["http://abc.execute-api.us-east-1.amazonaws.com", "https://example.com",
                   "https://abc.execute-api.us-east-1.amazonaws.com.evil.test",
                   "https://u@abc.execute-api.us-east-1.amazonaws.com",
                   "https://abc.execute-api.us-west-2.amazonaws.com",
                   "https://abc.execute-api.us-east-1.amazonaws.com:443",
                   "https://abc.execute-api.us-east-1.amazonaws.com?url=otro"]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(ValueError):
                smoke.Api(self.session, url)
        self.session.get_credentials.assert_not_called()
        self.assertIsNone(smoke.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_actual_request_is_sigv4_signed_and_unsigned_request_has_no_token(self):
        api = smoke.Api(self.session, "https://abc.execute-api.us-east-1.amazonaws.com")
        with patch.object(smoke.urllib.request, "build_opener") as build:
            response = build.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b"[]"
            self.assertEqual((200, []), api.call("/usuarios/api/usuarios"))
            signed = build.return_value.open.call_args.args[0]
            self.assertTrue(signed.get_header("Authorization").startswith("AWS4-HMAC-SHA256"))
            self.assertEqual("TOKEN_DE_PRUEBA", signed.get_header("X-amz-security-token"))
            api.call("/usuarios/api/usuarios", signed=False)
            unsigned = build.return_value.open.call_args.args[0]
            self.assertIsNone(unsigned.get_header("Authorization"))
            self.assertIsNone(unsigned.get_header("X-amz-security-token"))


class DeploymentTests(TestCase):
    def deploy(self, folder, plan, prefix=None):
        session = MagicMock(region_name="us-east-1")
        registry = f"{ACCOUNT}.dkr.ecr.us-east-1.amazonaws.com"
        cluster = {"ManagerInstanceId": "i-manager", "WorkerInstanceId": "i-worker", "Registry": registry,
                   "AppPasswordSecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:app",
                   "RootPasswordSecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:root"}
        runtime = Path(folder)
        def download(bucket, key, target):
            Path(target).write_text(json.dumps(plan), encoding="utf-8")
        session.client.return_value.download_file.side_effect = download
        args = SimpleNamespace(service=None, bucket="foodgo-test", prefix=prefix or f"releases/{SHA}/12345")
        with patch.object(cloud, "session", return_value=(session, ACCOUNT)), patch.object(cloud, "outputs", side_effect=[cluster, {"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/foodgo"}]), patch.object(cloud, "wait_nodes"), patch.object(cloud, "RUNTIME", runtime), patch.object(cloud, "run_on_manager") as run:
            cloud.deploy(args)
            return run.call_args.args[2]

    def test_valid_release_keeps_volume_and_strips_password_newline(self):
        plan = [{"service": service, "sha": SHA} for service in cloud.SERVICES]
        with TemporaryDirectory() as folder:
            script = self.deploy(folder, plan)
        self.assertIn("tr -d '\\r\\n'", script)
        self.assertNotIn("tr -d '\\\\r\\\\n'", script)
        self.assertIn("docker stack deploy --with-registry-auth", script)
        self.assertNotIn("docker volume rm", script)
        self.assertNotIn("docker system prune", script)
        self.assertNotIn("swarm leave", script)
        self.assertEqual(9, script.count("export IMAGE_"))

    def test_invalid_or_incomplete_release_never_reaches_manager(self):
        with TemporaryDirectory() as folder:
            for plan in [[], [{"service": s, "sha": SHA} for s in cloud.SERVICES[:-1]],
                         [{"service": s, "sha": "$(comando)"} for s in cloud.SERVICES]]:
                with self.subTest(plan=plan), self.assertRaises(ValueError):
                    self.deploy(folder, plan)
            with self.assertRaises(ValueError):
                self.deploy(folder, [], prefix="releases/../../otro")


class SourcePlanTests(TestCase):
    def test_missing_main_is_an_explicit_error_and_does_not_create_release(self):
        with patch.object(source_matrix.subprocess, "run", return_value=SimpleNamespace(stdout="")), TemporaryDirectory() as folder, patch.object(source_matrix, "ROOT", Path(folder)):
            with self.assertRaisesRegex(ValueError, "commit valido"):
                source_matrix.main()
            self.assertFalse((Path(folder) / ".runtime/images.json").exists())


if __name__ == "__main__":
    main()
