import * as esbuild from "esbuild";

const isWatch = process.argv.includes("--watch");

const config = {
    entryPoints: {
        "enrichment": "src/enrichment/index.tsx",
    },
    bundle: true,
    format: "esm",
    outdir: "../eclear/static",
    loader: { ".css": "text" },
    jsx: "automatic",
};

if (isWatch) {
    const ctx = await esbuild.context(config);
    await ctx.watch();
    console.log("esbuild watching...");
} else {
    await esbuild.build(config);
    console.log("Build complete:", Object.keys(config.entryPoints).map(k => `${k}.js`).join(", "));
}
