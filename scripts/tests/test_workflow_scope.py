"""Impide que una entrega documental reanude recursos AWS al fusionarse."""
from pathlib import Path
from fnmatch import fnmatchcase
from unittest import TestCase
import yaml

ROOT=Path(__file__).resolve().parents[2]

class CloudTriggerTests(TestCase):
    def setUp(self):
        self.workflow=yaml.load((ROOT/'.github/workflows/cloud.yml').read_text(encoding='utf-8'),Loader=yaml.BaseLoader)
        self.patterns=self.workflow['on']['push']['paths']

    def triggers(self,path):
        return any(fnmatchcase(path,pattern) for pattern in self.patterns)

    def test_exam_material_does_not_trigger_a_cloud_deployment(self):
        for file in ['README.md','docs/diagrama/FoodGo_Arquitectura.png',
                     'docs/EFT-Pruebas-y-grabacion.md',
                     'postman/eft/FoodGo-EFT-AWS.postman_collection.json',
                     'postman/tests/validate-eft.cjs',
                     'scripts/tests/test_workflow_scope.py',
                     '.github/workflows/ci.yml','.github/workflows/cloud.yml']:
            with self.subTest(file=file):
                self.assertFalse(self.triggers(file))

    def test_runtime_and_infrastructure_changes_remain_automatic(self):
        for file in ['infra/aws/cluster.yaml','infra/aws/mensajeria.yaml',
                     'swarm/nginx.conf','functions/notificaciones/pom.xml',
                     'scripts/cloud.py','scripts/registry.py','scripts/smoke.py',
                     'scripts/source_matrix.py','docker-stack.yml']:
            with self.subTest(file=file):
                self.assertTrue(self.triggers(file))

    def test_manual_execution_remains_available_and_main_is_the_only_push_branch(self):
        self.assertIn('workflow_dispatch',self.workflow['on'])
        self.assertEqual(['main'],self.workflow['on']['push']['branches'])
