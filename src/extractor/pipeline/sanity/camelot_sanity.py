import camelot
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv(usecwd=True), override=False)


def main():
    pdf_file = "/home/graham/workspace/experiments/extractor/src/extractor/pipeline/gold_standards/BHT_CV32A65X_reqs/BHT_CV32A65X_reqs.pdf"
    tables = camelot.read_pdf(
        pdf_file,
        pages="1-3",
        flavor="lattice",
        line_scale=15,          # lattice only
        process_background=False,
        strip_text="\n",        # clean up line breaks if needed
    )

    return tables
    



if __name__ == "__main__":
    tables = main()
