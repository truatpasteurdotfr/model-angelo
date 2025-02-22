"""
ModelAngelo hmm_search command.
Once you have already run model_angelo build_no_seq, this command
can help you search against a FASTA file that you provide.

You will need:
1) A ModelAngelo build_no_seq output directory, provide with --input-dir/--i/-i
2) A fasta sequence file to search, provide with --fasta-path/--f/-f
3) (Optional) An output directory for the results, provide with --output-dir/--o/-o
"""

import argparse
import os
import pyhmmer
import glob

import tqdm

from model_angelo.utils.misc_utils import (
    write_relion_job_exit_status,
    abort_if_relion_abort,
)


def add_args(parser):
    """
    Need to remove model_bundle_path as a positional argument. It should not be required.
    It should normally reside in ~/.cache/model_angelo/bundle or something.
    """
    main_args = parser.add_argument_group(
        "Main arguments",
        description="These are the only arguments a typical user will need.",
    )
    main_args.add_argument(
        "--input-dir",
        "-i",
        "--i",
        help="The input directory to this program, i.e. ModelAngelo build_no_seq output directory",
        type=str,
        required=True,
    )
    main_args.add_argument(
        "--fasta-path",
        "-f",
        "--f",
        help="Path to the FASTA file with all the sequences to search against",
        type=str,
        required=True,
    )
    main_args.add_argument(
        "--output-dir",
        "-o",
        "--o",
        help="Path to output directory of this program, i.e. where results are stored",
        type=str,
        default="output",
    )

    additional_args = parser.add_argument_group(
        "Additional arguments", description="These are sometimes useful."
    )
    additional_args.add_argument(
        "--alphabet",
        "-a",
        "--a",
        help="Alphabet type for the sequence file. Choose between amino/RNA/DNA",
        type=str,
        default="amino",
    )

    hmm_search_args = parser.add_argument_group(
        "HMMSearch arguments",
        description="These are the settings that go into HMMSearch, "
        "you can make it more or less sensitive.\n"
        "Please see http://eddylab.org/software/hmmer/Userguide.pdf",
    )

    hmm_search_args.add_argument("--F1", type=float, default=0.02)
    hmm_search_args.add_argument("--F2", type=float, default=0.001)
    hmm_search_args.add_argument("--F3", type=float, default=1e-5)
    hmm_search_args.add_argument("--E", type=float, default=10)
    hmm_search_args.add_argument("--T", type=float, default=None)

    advanced_args = parser.add_argument_group(
        "Advanced arguments",
        description="These should *not* be changed unless the user is aware of what they do.",
    )
    advanced_args.add_argument(
        "--config-path", "-c", "--c", help="config file", type=str, default=None
    )
    advanced_args.add_argument(
        "--model-bundle-name",
        type=str,
        default="original_no_seq",
        help="Inference model bundle name",
    )
    advanced_args.add_argument(
        "--model-bundle-path",
        type=str,
        default=None,
        help="Inference model bundle path. If this is set, --model-bundle-name is not used.",
    )

    # Below are RELION arguments, make sure to always add help=argparse.SUPPRESS

    parser.add_argument(
        "--pipeline-control",
        "--pipeline_control",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser


def main(parsed_args):
    print("---------------------------- ModelAngelo -----------------------------")
    print("By Kiarash Jamali, Scheres Group, MRC Laboratory of Molecular Biology")

    hmm_profile_dir = os.path.join(parsed_args.input_dir, "hmm_profiles")
    if not os.path.isdir(hmm_profile_dir):
        print(
            f"The directory {hmm_profile_dir} does not exist. "
            f"Are you sure that the output of model_angelo build_no_seq is in {parsed_args.input_dir}?"
        )
        write_relion_job_exit_status(
            parsed_args.output_dir,
            "FAILURE",
            pipeline_control=parsed_args.pipeline_control,
        )

    hmms = [
        (os.path.split(f)[-1].replace(".hmm", ""), pyhmmer.plan7.HMMFile(f).read())
        for f in glob.glob(f"{hmm_profile_dir}/*.hmm")
    ]

    alphabet = {
        "amino": pyhmmer.easel.Alphabet.amino(),
        "RNA": pyhmmer.easel.Alphabet.rna(),
        "DNA": pyhmmer.easel.Alphabet.dna(),
    }[parsed_args.alphabet]

    os.makedirs(parsed_args.output_dir, exist_ok=True)

    pruned_hmms = [k for k in hmms if k[1].alphabet == alphabet]

    with pyhmmer.easel.SequenceFile(parsed_args.fasta_path, alphabet=alphabet, digital=True) as sf:
        digital_sequences = sf.read_block()

    all_hits = pyhmmer.hmmer.hmmsearch(
        [hmm for name,hmm in pruned_hmms],
        digital_sequences,
        F1=parsed_args.F1,
        F2=parsed_args.F2,
        F3=parsed_args.F3,
        E=parsed_args.E,
        T=parsed_args.T,
    )
    for (hits, name) in tqdm.tqdm(zip(all_hits, [name for name,hmm in pruned_hmms])):
        if parsed_args.pipeline_control:
            abort_if_relion_abort(parsed_args.output_dir)
        with open(os.path.join(parsed_args.output_dir, f"{name}.hhr"), "wb") as f:
            hits.write(f)
        try:
            msa = hits.to_msa(alphabet)
            with open(os.path.join(parsed_args.output_dir, f"{name}.a2m"), "wb") as f:
                msa.write(f, "a2m")
        except:
            pass

    print("-" * 70)
    print("ModelAngelo hmm_search completed successfully!")
    print("-" * 70)
    print(f"You can view your results in {parsed_args.output_dir}")
    print(
        f"The results are named according to the chains in your ModelAngelo build_no_seq model"
    )

    if len(pruned_hmms) > 0:
        print(
            f"For example, for chain {pruned_hmms[0][0]}, the result is in "
            f"{os.path.join(parsed_args.output_dir, pruned_hmms[0][0] + '.hhr')}"
        )
    print("-" * 70)
    print("Enjoy!")

    write_relion_job_exit_status(
        parsed_args.output_dir, "SUCCESS", pipeline_control=parsed_args.pipeline_control
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__,
    )
    parsed_args = add_args(parser).parse_args()
    main(parsed_args)
