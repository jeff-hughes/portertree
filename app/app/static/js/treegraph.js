// from: https://stackoverflow.com/a/9899701
function docReady(fn) {
    // see if DOM is already available
    if (document.readyState === "complete" || document.readyState === "interactive") {
        // call on next available tick
        setTimeout(fn, 1);
    } else {
        document.addEventListener("DOMContentLoaded", fn);
    }
} 

if (typeof tree_width === "undefined") {
    tree_width = 800;
}
if (typeof tree_height === "undefined") {
    tree_height = 300;
}
if (typeof tree_nodeWidth === "undefined") {
    tree_nodeWidth = 170;
}

tree_options = {
    target: ".treegraph",
    debug: true,
    width: tree_width,
    height: tree_height,
    nodeWidth: tree_nodeWidth,
    callbacks: {
        textRenderer: function(name, extra, textClass) {
            text = "<p class='" + textClass + "'>";
            if (extra && extra.url) {
                text += "<a href='" + extra.url + "'>" + name + "</a>";
            } else {
                text += name;
            }
            text += "</p>";
            return text;
        },
        nodeRenderer: function(name, x, y, height, width, extra, id, nodeClass, textClass, textRenderer) {
            let node = '';
            node += '<div class="node ' + nodeClass + '" id="node' + id + '">\n';
            node += textRenderer(name, extra, textClass);
            node += '</div>';
            return node;
        }
    }
};

docReady(function() {
    tree = dTree.init(tree_data, tree_options);
});