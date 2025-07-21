/**
 * Experimental script to deconstruct a minified JavaScript file into modular components
 * for analysis. This is purely an experiment and not intended to violate any terms
 * or cause issues with third-party software.
 *
 * Target file: input/cli.js (or any minified .js file)
 *
 * Usage:
 *   node src/deconstruct_pipeline.js <input_file> [--output-dir <path>]
 *   Example: node src/deconstruct_pipeline.js input/cli.js --output-dir output/custom
 *   Run `node src/deconstruct_pipeline.js --help` for details.
 *
 * Description:
 * This script processes a minified JavaScript file through a pipeline:
 * 1. Prettier: Formats code for readability.
 * 2. Webcrack: Deobfuscates variable names.
 * 3. Tree-sitter: Splits code into modular files (functions, classes, etc.).
 * 4. Vertex AI: Generates LLM descriptions for each file using Google Vertex AI (via LangChain.js).
 * It creates a pseudo-sourcemap, dependency graph, and LLM analysis.
 *
 * Third-party documentation:
 * - Prettier: https://prettier.io/docs/en/
 * - Webcrack: https://github.com/j4k0xb/webcrack
 * - Tree-sitter: https://tree-sitter.github.io/
 * - LangChain.js (Vertex AI): https://js.langchain.com/docs/integrations/chat/google_vertex_ai
 * - Yargs: https://yargs.js.org/
 *
 * Expected input: Minified JavaScript files with:
 * - Short variable names (e.g., zZ6, QZ6, J1, A)
 * - No whitespace or comments
 * - Compressed syntax (e.g., import{createRequire as zZ6}from"node:module";var QZ6=Object.create;...)
 *
 * Expected output: A directory (default: output/deconstructed_output/) with:
 * - 1_minified_prettier.js (formatted code)
 * - 2_minified_webcrack.js (deobfuscated code)
 * - 3_minified_tree_sitter/ (modular files: functions/, classes/, etc.)
 * - sourcemap.json (maps files to original lines)
 * - dependency_graph.json (file relationships)
 * - llm_analysis.md (LLM descriptions for each file)
 * - README.md (setup and usage instructions)
 */

// Node.js built-in modules
const fs = require('fs').promises; // Async file operations (Python: asyncio.open)
const path = require('path'); // Path manipulation (Python: os.path)

// External npm modules
require('dotenv').config(); // Load .env variables (Python: python-dotenv)
const prettier = require('prettier'); // Code formatting
const { deobfuscate } = require('webcrack'); // Deobfuscation
const Parser = require('tree-sitter'); // AST parsing
const JavaScript = require('tree-sitter-javascript'); // JavaScript grammar for Tree-sitter
const { ChatVertexAI } = require('@langchain/google-vertexai'); // Vertex AI LLM calls
const yargs = require('yargs'); // CLI argument parsing (Python: argparse)

// Initialize Tree-sitter parser
const parser = new Parser();
parser.setLanguage(JavaScript);

// Parse CLI arguments with yargs
const argv = yargs
    .usage('Usage: node $0 <input_file> [--output-dir <path>]')
    .demandCommand(1, 'You must provide an input JavaScript file.')
    .option('output-dir', {
        type: 'string',
        description: 'Output directory for results',
        default: 'output/deconstructed_output',
    })
    .check((argv) => {
        if (!argv._[0].endsWith('.js')) {
            throw new Error('Input file must be a .js file.');
        }
        return true;
    })
    .help()
    .argv;

// Input and output paths
const inputFile = argv._[0];
const outputDir = argv.outputDir;
const prettierOutput = path.join(outputDir, '1_minified_prettier.js');
const webcrackOutput = path.join(outputDir, '2_minified_webcrack.js');
const treeSitterOutputDir = path.join(outputDir, '3_minified_tree_sitter');

// Load Vertex AI credentials
const vertexCredentialsPath = process.env.VERTEX_AI_CREDENTIALS_PATH || path.join(__dirname, '../config/vertex_ai_service_account.json');
let vertexCredentials;
async function loadCredentials() {
    try {
        const data = await fs.readFile(vertexCredentialsPath, 'utf8'); // Python: open().read()
        vertexCredentials = JSON.parse(data);
    } catch (error) {
        console.error(`Failed to load credentials from ${vertexCredentialsPath}:`, error.message);
        process.exit(1);
    }
}

// Initialize Vertex AI model
const vertexModel = new ChatVertexAI({
    model: 'gemini-1.5-pro', // or 'gemini-pro'
    projectId: vertexCredentials?.project_id || 'your-project-id',
    location: 'us-central1', // Replace with your region
    credentials: vertexCredentials,
    maxOutputTokens: 1000,
});

// Validate input file
async function validateInputFile(inputFile) {
    try {
        await fs.access(inputFile); // Python: os.access
    } catch {
        console.error(`Error: Input file ${inputFile} does not exist or is inaccessible.`);
        process.exit(1);
    }
}

// Step 1: Run Prettier
async function runPrettier(input, output) {
    const sourceCode = await fs.readFile(input, 'utf8');
    const formattedCode = prettier.format(sourceCode, {
        parser: 'babel',
        semi: true,
        trailingComma: 'es5',
        singleQuote: true,
    });
    await fs.mkdir(path.dirname(output), { recursive: true });
    await fs.writeFile(output, formattedCode);
    console.log(`Saved ${output}`);
    return formattedCode;
}

// Step 2: Run Webcrack
async function runWebcrack(input, output) {
    const sourceCode = await fs.readFile(input, 'utf8');
    const result = await deobfuscate(sourceCode);
    await fs.mkdir(path.dirname(output), { recursive: true });
    await fs.writeFile(output, result.code);
    console.log(`Saved ${output}`);
    return result.code;
}

// Step 3: Tree-sitter Deconstruction
async function runTreeSitter(sourceCode, outputDir) {
    const tree = parser.parse(sourceCode);
    const rootNode = tree.rootNode;

    const sourcemap = {
        originalFile: path.basename(inputFile),
        chunks: [],
    };
    const chunks = [];

    // Extract code snippet from a node (Python: string slicing)
    const extractCode = (node) => sourceCode.slice(node.startIndex, node.endIndex);

    // Sanitize filenames for safe output (Python: re.sub)
    const sanitizeFilename = (name) =>
        name.replace(/[^a-zA-Z0-9_]/g, '_').replace(/^_+|_+$/g, '') || 'unnamed';

    // Map node types to output directories
    const nodeTypes = {
        function_declaration: 'function',
        method_definition: 'method',
        arrow_function: 'arrow_function',
        class_declaration: 'class',
        variable_declaration: 'variable',
        lexical_declaration: 'constant',
        export_statement: 'export',
        import_statement: 'import',
    };

    // Process a single node recursively
    function processNode(node, depth = 0, parentName = '') {
        const type = nodeTypes[node.type] || 'other';
        let name = node.childForFieldName('name')?.text || '';

        if (type === 'variable' || type === 'constant') {
            name = node.children
                .filter((child) => child.type === 'variable_declarator')
                .map((child) => child.childForFieldName('name')?.text)
                .join('_') || 'anonymous';
        } else if (type === 'export' || type === 'import') {
            name = type + '_' + (node.children[1]?.type || 'default');
        } else if (type === 'arrow_function') {
            name = parentName ? `${parentName}_arrow` : 'anonymous_arrow';
        }

        if (type !== 'other') {
            const chunk = {
                name: name || `chunk_${chunks.length}`,
                type,
                code: extractCode(node),
                startLine: node.startPosition.row + 1,
                endLine: node.endPosition.row + 1,
                parent: parentName,
            };
            chunks.push(chunk);
            sourcemap.chunks.push({
                id: chunks.length - 1,
                name: chunk.name,
                type: chunk.type,
                file: `${type}s/${sanitizeFilename(chunk.name)}.js`,
                startLine: chunk.startLine,
                endLine: chunk.endLine,
            });
        }

        node.children.forEach((child) => processNode(child, depth + 1, name || parentName));
    }

    // Handle base code (code not captured in specific nodes)
    async function processBaseCode() {
        processNode(rootNode);

        const usedRanges = chunks
            .map((chunk) => [chunk.startLine, chunk.endLine])
            .sort((a, b) => a[0] - b[0]);
        let baseCode = '';
        let lastEnd = 0;
        for (const [start, end] of usedRanges) {
            if (lastEnd < start - 1) {
                const lines = sourceCode.split('\n').slice(lastEnd, start - 1).join('\n');
                baseCode += lines + '\n';
            }
            lastEnd = end;
        }
        if (lastEnd < sourceCode.split('\n').length) {
            baseCode += sourceCode.split('\n').slice(lastEnd).join('\n');
        }
        if (baseCode.trim()) {
            chunks.push({
                name: 'base',
                type: 'base',
                code: baseCode,
                startLine: 1,
                endLine: sourceCode.split('\n').length,
            });
            sourcemap.chunks.push({
                id: chunks.length - 1,
                name: 'base',
                type: 'base',
                file: 'base/base.js',
                startLine: 1,
                endLine: sourceCode.split('\n').length,
            });
        }
    }

    // Save chunks to files
    async function saveChunks() {
        const typeDirs = [...new Set(chunks.map((chunk) => chunk.type))];
        for (const type of typeDirs) {
            await fs.mkdir(path.join(outputDir, `${type}s`), { recursive: true });
        }

        for (const chunk of chunks) {
            const filename = path.join(outputDir, `${chunk.type}s`, `${sanitizeFilename(chunk.name)}.js`);
            const comment = `// ${chunk.type}: ${chunk.name}\n// Lines ${chunk.startLine}-${chunk.endLine} from ${path.basename(inputFile)}\n`;
            await fs.writeFile(filename, comment + chunk.code);
            console.log(`Saved ${filename}`);
        }

        await fs.writeFile(
            path.join(outputDir, 'sourcemap.json'),
            JSON.stringify(sourcemap, null, 2)
        );
        console.log(`Saved sourcemap.json`);
    }

    await processBaseCode();
    await saveChunks();
    return chunks;
}

// Step 4: Generate JSDoc Comments
async function addJSDocComments(inputDir) {
    const files = [];
    async function walkDir(dir) {
        const entries = await fs.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                await walkDir(fullPath);
            } else if (entry.name.endsWith('.js')) {
                files.push(fullPath);
            }
        }
    }
    await walkDir(inputDir);

    for (const filePath of files) {
        const code = await fs.readFile(filePath, 'utf8');
        const tree = parser.parse(code);
        let newCode = code;
        for (const node of tree.rootNode.children) {
            if (node.type === 'function_declaration' || node.type === 'method_definition') {
                const name = node.childForFieldName('name')?.text || 'anonymous';
                const params = node.childForFieldName('parameters')?.children
                    .filter((child) => child.type === 'identifier')
                    .map((child) => child.text)
                    .join(', ') || '';
                const jsdoc = `/**\n * Function ${name}\n * @param {any} ${params.split(', ').join('\n * @param {any} ')}\n * @returns {any}\n */\n`;
                newCode = newCode.slice(0, node.startIndex) + jsdoc + newCode.slice(node.startIndex);
            }
        }
        await fs.writeFile(filePath, newCode);
        console.log(`Added JSDoc to ${filePath}`);
    }
}

// Step 5: Generate Dependency Graph
async function generateDependencyGraph(inputDir, outputFile) {
    const graph = { nodes: [], edges: [] };
    const files = [];
    async function walkDir(dir) {
        const entries = await fs.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                await walkDir(fullPath);
            } else if (entry.name.endsWith('.js')) {
                files.push(fullPath);
            }
        }
    }
    await walkDir(inputDir);

    for (const filePath of files) {
        const code = await fs.readFile(filePath, 'utf8');
        const tree = parser.parse(code);
        const name = path.basename(filePath, '.js');
        graph.nodes.push({ id: name, file: filePath });
        tree.rootNode.walk().forEach((node) => {
            if (node.type === 'identifier') {
                const id = node.text;
                if (files.some((f) => path.basename(f, '.js') === id)) {
                    graph.edges.push({ from: name, to: id });
                }
            }
        });
    }

    await fs.writeFile(outputFile, JSON.stringify(graph, null, 2));
    console.log(`Saved ${outputFile}`);
}

// Step 6: LLM Analysis with Per-File Descriptions using Vertex AI
async function runLLMAnalysis(inputDir, sourcemapFile, dependencyGraphFile, outputFile, chunks) {
    const sourcemap = JSON.parse(await fs.readFile(sourcemapFile, 'utf8'));
    const dependencyGraph = JSON.parse(await fs.readFile(dependencyGraphFile, 'utf8'));

    let analysis = `# LLM Analysis of ${sourcemap.originalFile}\n\n`;
    analysis += `**Note**: This is an experimental analysis of a minified JavaScript file. No proprietary code is shared or misused.\n\n`;

    // Simple retry logic for LLM calls (Python: tenacity.retry)
    async function invokeWithRetry(prompt, maxRetries = 3) {
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                const response = await vertexModel.invoke([{ role: 'user', content: prompt }]);
                return response.content || 'No response from LLM';
            } catch (error) {
                if (attempt === maxRetries) {
                    throw error;
                }
                const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
                console.warn(`Retry ${attempt}/${maxRetries} for LLM call: ${error.message}`);
                await new Promise((resolve) => setTimeout(resolve, delay));
            }
        }
    }

    for (const chunk of chunks) {
        const filePath = path.join(inputDir, `${chunk.type}s`, `${sanitizeFilename(chunk.name)}.js`);
        const code = await fs.readFile(filePath, 'utf8');
        const prompt = `
Analyze the following JavaScript code from file ${filePath} (originally from ${sourcemap.originalFile}, lines ${chunk.startLine}-${chunk.endLine}).

**Code**:
\`\`\`javascript
${code}
\`\`\`

**Context**:
- The original code was minified (short variable names like zZ6, no whitespace) and obfuscated.
- It was processed by Prettier, Webcrack, and Tree-sitter to create this file.
- Type: ${chunk.type}, Name: ${chunk.name}
- Dependencies: ${JSON.stringify(dependencyGraph.edges.filter((e) => e.from === chunk.name), null, 2)}
- Sourcemap: Maps to lines ${chunk.startLine}-${chunk.endLine} in the original file.

**Tasks**:
1. **Purpose**: What does this code do? (e.g., module loader, utility function)
2. **Role**: What is its role in the codebase? (e.g., CLI setup, module interoperability)
3. **Key Patterns**: Identify notable patterns (e.g., import {createRequire}, Object.defineProperty).
4. **Challenges**: What makes this code hard to understand without a source map?
5. **Hypotheses**: If unclear, hypothesize its function based on patterns.

**Output**:
- Write a concise Markdown section for this file.
- Include Purpose, Role, Key Patterns, Challenges, and Hypotheses.
`;

        try {
            const content = await invokeWithRetry(prompt);
            analysis += `## File: ${chunk.type}s/${sanitizeFilename(chunk.name)}.js\n\n`;
            analysis += content + '\n\n';
        } catch (error) {
            console.error(`LLM analysis failed for ${filePath}:`, error.message);
            analysis += `## File: ${chunk.type}s/${sanitizeFilename(chunk.name)}.js\n\n`;
            analysis += `**Error**: Failed to analyze due to ${error.message}\n\n`;
        }
    }

    analysis += `## Codebase Overview\n\n`;
    analysis += `The codebase appears to be a Node.js CLI application, likely for interacting with an AI model (based on the input file path). The pipeline split it into modular files, revealing:
- **Imports**: Module interoperability (e.g., createRequire).
- **Functions**: Utilities for object manipulation or CLI logic.
- **Challenges**: Obfuscated names and missing comments limit clarity.
- **Improvements**: Use meaningful names, add JSDoc, or provide a true source map.\n`;

    await fs.writeFile(outputFile, analysis);
    console.log(`Saved LLM analysis to ${outputFile}`);
}

// Run Pipeline
async function runPipeline() {
    console.log('Starting pipeline...');

    // Load credentials
    await loadCredentials();

    // Validate input
    await validateInputFile(inputFile);

    // Run steps
    const prettierCode = await runPrettier(inputFile, prettierOutput);
    const webcrackCode = await runWebcrack(prettierOutput, webcrackOutput);
    const chunks = await runTreeSitter(webcrackCode, treeSitterOutputDir);
    await addJSDocComments(treeSitterOutputDir);
    await generateDependencyGraph(treeSitterOutputDir, path.join(outputDir, 'dependency_graph.json'));
    await runLLMAnalysis(
        treeSitterOutputDir,
        path.join(outputDir, 'sourcemap.json'),
        path.join(outputDir, 'dependency_graph.json'),
        path.join(outputDir, 'llm_analysis.md'),
        chunks
    );
    await generateReadme();
    console.log('Pipeline complete.');
}

// Generate README.md
async function generateReadme() {
    const readmeContent = `
# JavaScript Deconstruction Pipeline

**Note**: This is an experimental tool for analyzing minified JavaScript files. It processes a minified .js file (e.g., input/cli.js) for educational purposes only. Ensure you have permission to analyze the input file.

## WHY
To learn more about how to reverse engineer a minified JavaScript file by breaking it into smaller, more manageable files, approximating a source map, and using an LLM to analyze the code.

## Purpose
This script deconstructs a minified JavaScript file into modular components to approximate a source map and generate LLM-based analysis. It processes the input through:
1. **Prettier**: Formats the code for readability.
2. **Webcrack**: Deobfuscates variable names.
3. **Tree-sitter**: Splits code into files by type (functions, classes, etc.).
4. **LLM Analysis**: Uses Google Vertex AI (via LangChain.js) for per-file descriptions.

## Prerequisites
- Node.js v22.15.0 or later
- Google Vertex AI service account JSON key (in config/vertex_ai_service_account.json)

## Installation
1. Clone this repository or copy the project files.
2. Initialize a Node.js project (if not already done):
   \`\`\`bash
   npm init -y
   \`\`\`
3. Install dependencies:
   \`\`\`bash
   npm install
   \`\`\`
   This uses package.json to install prettier, webcrack, tree-sitter, @langchain/google-vertexai, dotenv, yargs, etc.
4. Place your Vertex AI service account JSON key in config/vertex_ai_service_account.json.
5. Create a .env file in the project root:
   \`\`\`env
   VERTEX_AI_CREDENTIALS_PATH=config/vertex_ai_service_account.json
   \`\`\`
6. Add .env, config/vertex_ai_service_account.json, node_modules/, and output/ to .gitignore.

## Project Structure
\`\`\`
project-root/
├── src/                          # Source code
│   ├── deconstruct_pipeline.js   # Main script
│   └── utils/                   # Utility modules (optional)
├── config/                      # Configuration files
│   ├── .env                     # Environment variables
│   └── vertex_ai_service_account.json # Vertex AI credentials
├── input/                       # Input files
│   └── cli.js                   # Example minified JS
├── output/                      # Output directory
│   └── deconstructed_output/    # Generated files
├── tests/                       # Test files (optional)
│   └── deconstruct_pipeline.test.js # Placeholder
├── .gitignore                   # Git ignore file
├── package.json                 # Dependencies and scripts
├── README.md                    # Documentation
└── .eslintrc.json               # ESLint configuration (optional)
\`\`\`

## Usage
Run the script with a minified JavaScript file:
\`\`\`bash
node src/deconstruct_pipeline.js <input_file> [--output-dir <path>]
\`\`\`
Example:
\`\`\`bash
node src/deconstruct_pipeline.js input/cli.js --output-dir output/custom
\`\`\`
Run \`node src/deconstruct_pipeline.js --help\` for options.

## Expected Input
Minified JavaScript files with:
- Short variable names (e.g., zZ6, QZ6, J1, A)
- No whitespace or comments
- Compressed syntax (e.g., \`import{createRequire as zZ6}from"node:module";var QZ6=Object.create;...\`)

## Output Structure
The script creates a directory (default: output/deconstructed_output/) with:
- \`1_minified_prettier.js\`: Formatted code.
- \`2_minified_webcrack.js\`: Deobfuscated code.
- \`3_minified_tree_sitter/\`: Modular files in subdirectories:
  - \`functions/\`: Function declarations/methods.
  - \`classes/\`: Class declarations.
  - \`imports/\`: Import statements.
  - \`exports/\`: Export statements.
  - \`variables/\`: Variable declarations.
  - \`constants/\`: Const/let declarations.
  - \`base/\`: Miscellaneous code.
- \`sourcemap.json\`: Maps files to original line numbers.
- \`dependency_graph.json\`: File relationships.
- \`llm_analysis.md\`: LLM descriptions for each file.
- \`README.md\`: This file.

## Example Output
\`\`\`
output/deconstructed_output/
├── 1_minified_prettier.js
├── 2_minified_webcrack.js
├── 3_minified_tree_sitter/
│   ├── functions/
│   │   ├── module_helper.js
│   │   ├── another_function.js
│   ├── imports/
│   │   ├── import_createRequire.js
│   ├── base/
│   │   ├── base.js
├── sourcemap.json
├── dependency_graph.json
├── llm_analysis.md
├── README.md
\`\`\`

## Notes
- The LLM analysis requires a Google Vertex AI service account JSON key (see https://cloud.google.com/vertex-ai/docs).
- The script assumes the input is a valid minified JavaScript file.
- For large files, monitor memory usage during Tree-sitter parsing.
- Use .env for secure credential path storage with dotenv.
  `;
    await fs.writeFile(path.join(outputDir, 'README.md'), readmeContent);
    console.log(`Saved README.md`);
}

// Execute pipeline
runPipeline().catch((err) => console.error('Pipeline error:', err));