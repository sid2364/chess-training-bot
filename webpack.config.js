const path = require("path");
module.exports = {
  entry: "./chess_trainer/static/ui/src/index.jsx",
  output: {
    path: path.resolve(__dirname, "./chess_trainer/static/ui/dist"),
    filename: "bundle.js",
    publicPath: "/static/ui/dist/"
  },
  module: {
    rules: [
    {
      test: /\.(js|jsx)$/,
      exclude: /node_modules/,
      use: {
        loader: "babel-loader",
        options: {
          presets: ["@babel/preset-react"]
        }
      }
    }
    ]
  },
  resolve: { extensions: [".js", ".jsx"] }
};
