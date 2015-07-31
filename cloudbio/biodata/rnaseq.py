"""Prepare supplemental files to work with RNA-seq transcriptome experiments.

Retrieves annotations in a format usable by Cufflinks, using repositories
provided by Illumina:

http://cufflinks.cbcb.umd.edu/igenomes.html
"""
import os

from fabric.api import cd

from cloudbio.custom import shared
from cloudbio.fabutils import warn_only

VERSIONS = {"rn5": "2014-07-20",
            "GRCh37": "2014-07-14",
            "hg19": "2014-07-17",
            "mm10": "2014-07-14",
            "canFam3": "2014-07-20"}
VERSIONS_SMALLRNA = {"hg19": "2015-08-01",
                     "mm10": "2015-08-01"}

def download_transcripts(genomes, env):
    folder_name = "rnaseq"
    genome_dir = os.path.join(env.data_files, "genomes")
    for (orgname, gid, manager) in ((o, g, m) for (o, g, m) in genomes
                                    if m.config.get("rnaseq", False)):
        version = VERSIONS.get(gid, "")
        base_url = "https://s3.amazonaws.com/biodata/annotation/{gid}-rnaseq-{version}.tar.xz"
        org_dir = os.path.join(genome_dir, orgname)
        tx_dir = os.path.join(org_dir, gid, folder_name)
        version_dir = "%s-%s" % (tx_dir, version)
        if not env.safe_exists(version_dir):
            with cd(org_dir):
                has_rnaseq = _download_annotation_bundle(env, base_url.format(gid=gid, version=version), gid)
                if version and has_rnaseq:
                    _symlink_version(env, tx_dir, version_dir)
        if version:
            _symlink_refgenome(env, gid, org_dir)

        version_srnaseq = VERSIONS_SMALLRNA.get(gid, "")
        if version_srnaseq:
            tx_dir = os.path.join(org_dir, gid, "srnaseq")
            version_dir = "%s-%s" % (tx_dir, version_srnaseq)
            gtf_file = os.path.join(version_dir, "srna-transcripts.gtf")
            if not env.safe_exists(gtf_file):
                env.safe_sudo("mkdir -p %s" % version_dir, user=env.user)
                with cd(version_dir):
                    has_srnaseq = _download_srnaseq(env, version_dir, gid)
                    if has_srnaseq:
                        _symlink_version(env, tx_dir, version_dir)

def _symlink_refgenome(env, gid, org_dir):
    """Provide symlinks back to reference genomes so tophat avoids generating FASTA genomes.
    """
    for aligner in ["bowtie", "bowtie2"]:
        aligner_dir = os.path.join(org_dir, gid, aligner)
        if env.safe_exists(aligner_dir):
            with cd(aligner_dir):
                for ext in ["", ".fai"]:
                    orig_seq = os.path.join(os.pardir, "seq", "%s.fa%s" % (gid, ext))
                    if env.safe_exists(orig_seq) and not env.safe_exists(os.path.basename(orig_seq)):
                        env.safe_run("ln -sf %s" % orig_seq)

def _symlink_version(env, tx_dir, version_dir):
    """Symlink the expected base output directory to our current version.
    """
    if env.safe_exists(tx_dir):
        env.safe_run("rm -rf %s" % tx_dir)
    with cd(os.path.dirname(version_dir)):
        env.safe_run("ln -sf %s %s" % (os.path.basename(version_dir), os.path.basename(tx_dir)))

def _download_annotation_bundle(env, url, gid):
    """Download bundle of RNA-seq data from S3 biodata/annotation
    """
    tarball = shared._remote_fetch(env, url, allow_fail=True)
    if tarball and env.safe_exists(tarball):
        env.logger.info("Extracting RNA-seq references: %s" % tarball)
        env.safe_run("xz -dc %s | tar -xpf -" % tarball)
        env.safe_run("rm -f %s" % tarball)
        return True
    else:
        env.logger.warn("RNA-seq transcripts not available for %s" % gid)
        return False

def _download_srnaseq(env, version_dir, gid):
    """Download bundle of small RNA-seq data from seqcluster installation
    """
    url = "http://raw.githubusercontent.com/lpantano/seqcluster/master/scripts/%s.sh" % gid
    env.logger.warn(url)
    bash_script = shared._remote_fetch(env, url, allow_fail=True)
    if bash_script and env.safe_exists(bash_script):
        env.logger.info("Extracting small RNA-seq references: %s" % gid)
        env.safe_run("bash %s" % bash_script)
        env.safe_run("rm -f %s" % bash_script)
        return True
    else:
        env.logger.warn("small RNA-seq transcripts not available for %s" % gid)
        return False

