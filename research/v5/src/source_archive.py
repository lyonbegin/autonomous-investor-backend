"""Read actual TradingView Pine byte streams from a verified archive, never infer from titles.

Each archive member is explicitly addressed by an original manifest; original bytes are
not normalized or redistributed to GitHub. The evidence bundle remains local to its user.
"""
from __future__ import annotations
import hashlib, json, pathlib, re, zipfile

IDS = re.compile(r'^[A-Za-z0-9_-]{4,40}$')
PINNED = {'0CVvd49h':'06728ba8446771d2e45c63f2fca0d8cce378c96b445836f47c82e279285c1852'}

class PineSourceError(ValueError): pass

class PineArchive:
    def __init__(self, path):
        self.path=pathlib.Path(path)
        if not self.path.is_file(): raise FileNotFoundError(self.path)
        with self.path.open('rb') as f:
            self.archive_sha256=hashlib.file_digest(f, 'sha256').hexdigest()

    def load(self, source_id):
        if not IDS.fullmatch(source_id): raise PineSourceError('Unsafe source ID')
        stem=f'strategies/{source_id}'
        member=stem+'/original/strategy.pine'
        manpath=stem+'/manifest.json'
        with zipfile.ZipFile(self.path) as z:
            names=z.namelist()
            if names.count(member)!=1 or names.count(manpath)!=1:
                return {'status':'SOURCE_MISSING_OR_DUPLICATED','source_id':source_id,'archive_sha256':self.archive_sha256},None
            m=json.loads(z.read(manpath))
            raw=z.read(member)
        sha=hashlib.sha256(raw).hexdigest()
        if m.get('script_id')!=source_id:
            return {'status':'MANIFEST_ID_MISMATCH','source_id':source_id,'manifest_id':m.get('script_id')},None
        if m.get('pine_sha256')!=sha:
            return {'status':'MANIFEST_SHA_MISMATCH','source_id':source_id,'actual_sha256':sha,'manifest_sha256':m.get('pine_sha256')},None
        if source_id in PINNED and sha!=PINNED[source_id]:
            return {'status':'PREVIOUSLY_PINNED_SHA_MISMATCH','source_id':source_id,'actual_sha256':sha},None
        try: text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            return {'status':'UNSUPPORTED_ENCODING','source_id':source_id,'actual_sha256':sha},None
        ver=re.search(r'(?m)^\s*//\s*@version\s*=\s*(\d+)',text)
        annotated=str(m.get('original_version_annotation','')).strip()
        if ver and annotated and ver.group(1)!=annotated:
            return {'status':'PINE_VERSION_CONFLICT','source_id':source_id,'manifest_version':annotated,'source_version':ver.group(1)},None
        # Only exact hashed original bytes are accepted; do not infer permission to republish.
        return {'status':'SOURCE_SHA_VERIFIED','source_id':source_id,'sha256':sha,'bytes':len(raw),
                'line_count':len(text.splitlines()),'pine_version':int(ver.group(1)) if ver else None,
                'source_member':member,'manifest_member':manpath,'archive_sha256':self.archive_sha256,
                'manifest_original_state':m.get('original_source_state'),
                'original_source_origin':m.get('pine_source_origin'),
                'source_url':m.get('tradingview_url'),
                'license_status':'LICENSE_AND_PLATFORM_REUSE_RIGHTS_NOT_REVALIDATED'},text
