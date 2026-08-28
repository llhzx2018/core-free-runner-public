from pathlib import Path


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise SystemExit(f'missing baseline reconcile anchor: {label}')
    return source.replace(old, new, 1)


# CommonBaselineV2 must compare live runtime facts against the existing dynamic
# VF_PROJECT authority. The original V2 adoption source was sealed at Schema 2;
# pinning that historical number forever would turn every legitimate migration
# into false DATA/HEALTH/VERSION drift.
p = Path('src/Application/Operations/CommonBaselineV2.php')
s = p.read_text()
s = replace_once(
    s,
    "        $schema = (int)$this->pdo->query('SELECT MAX(version) FROM schema_migrations')->fetchColumn();\n        $driver = (string)$this->pdo->getAttribute(PDO::ATTR_DRIVER_NAME);\n",
    "        $schema = (int)$this->pdo->query('SELECT MAX(version) FROM schema_migrations')->fetchColumn();\n        $declaredSchema = $this->declaredSchema();\n        $driver = (string)$this->pdo->getAttribute(PDO::ATTR_DRIVER_NAME);\n",
    'declared schema load',
)
s = replace_once(
    s,
    "                $driver === 'sqlite' && $schema === 2 ? 'PASS' : 'DRIFT',\n                'SQLite remains the project data authority and Schema 2 remains unchanged.',\n                ['driver'=>$driver,'schema'=>$schema],\n",
    "                $driver === 'sqlite' && $declaredSchema !== null && $schema === $declaredSchema ? 'PASS' : 'DRIFT',\n                'SQLite remains the project data authority; live schema must match the declared dynamic project schema.',\n                ['driver'=>$driver,'schema'=>$schema,'declared_schema'=>$declaredSchema],\n",
    'DATA dynamic schema',
)
s = replace_once(
    s,
    "                $integrity === 'ok' && $schema === 2 && str_contains($publicIndex, \"if(\\$path==='/health')\") ? 'PASS' : 'DRIFT',\n                'Runtime health derives from live SQLite integrity, schema and application version; the existing /health endpoint remains canonical.',\n                ['database_integrity'=>$integrity,'schema'=>$schema],\n",
    "                $integrity === 'ok' && $declaredSchema !== null && $schema === $declaredSchema && str_contains($publicIndex, \"if(\\$path==='/health')\") ? 'PASS' : 'DRIFT',\n                'Runtime health derives from live SQLite integrity, declared schema and application version; the existing /health endpoint remains canonical.',\n                ['database_integrity'=>$integrity,'schema'=>$schema,'declared_schema'=>$declaredSchema],\n",
    'HEALTH dynamic schema',
)
s = replace_once(
    s,
    "                trim($this->version) !== '' && $schema === 2 ? 'PASS' : 'DRIFT',\n                'Application version and schema version remain separate runtime facts.',\n                ['version'=>$this->version,'schema'=>$schema],\n",
    "                trim($this->version) !== '' && $declaredSchema !== null && $schema === $declaredSchema ? 'PASS' : 'DRIFT',\n                'Application version and schema version remain separate runtime facts; schema is checked against dynamic project authority.',\n                ['version'=>$this->version,'schema'=>$schema,'declared_schema'=>$declaredSchema],\n",
    'VERSION dynamic schema',
)
s = replace_once(
    s,
    "    private function readRuntimeFile(string $relativePath): string\n",
    "    private function declaredSchema(): ?int\n    {\n        $project = $this->readRuntimeFile('VF_PROJECT.json');\n        if ($project === '') {\n            return null;\n        }\n        $decoded = json_decode($project, true);\n        if (!is_array($decoded)) {\n            return null;\n        }\n        $schema = $decoded['schema'] ?? null;\n        if (is_int($schema) && $schema > 0) {\n            return $schema;\n        }\n        if (is_string($schema) && ctype_digit($schema) && (int)$schema > 0) {\n            return (int)$schema;\n        }\n        return null;\n    }\n\n    private function readRuntimeFile(string $relativePath): string\n",
    'declared schema helper',
)
p.write_text(s)


# The baseline self-test validates semantic authority alignment, not the
# historical V2-adoption snapshot version/schema.
p = Path('bin/common-baseline-v2-self-test.php')
s = p.read_text()
s = replace_once(
    s,
    "$report = (new CommonBaselineV2($pdo, $config, $version))->resolve();\n\n$assert($version === '0.1.6', 'Version must remain 0.1.6');\n$assert((int)$pdo->query('SELECT MAX(version) FROM schema_migrations')->fetchColumn() === 2, 'Schema must remain 2');\n",
    "$report = (new CommonBaselineV2($pdo, $config, $version))->resolve();\n$project = json_decode((string)file_get_contents($basePath . '/VF_PROJECT.json'), true);\n$declaredVersion = is_array($project) ? trim((string)($project['version'] ?? '')) : '';\n$declaredSchema = is_array($project) ? (int)($project['schema'] ?? 0) : 0;\n$liveSchema = (int)$pdo->query('SELECT MAX(version) FROM schema_migrations')->fetchColumn();\n\n$assert($declaredVersion !== '' && $version === $declaredVersion, 'Version must match dynamic VF_PROJECT authority');\n$assert($declaredSchema > 0 && $liveSchema === $declaredSchema, 'Live schema must match dynamic VF_PROJECT authority');\n",
    'self-test dynamic identity',
)
p.write_text(s)
