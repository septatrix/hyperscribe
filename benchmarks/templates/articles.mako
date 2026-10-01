<%def name="topic_list(topics)">
<div>
% for index, topic in enumerate(topics):
  <span>${topic}</span>${", " if index < len(topics) - 1 else ""}
% endfor
</div>
</%def>
<%inherit file="base.mako"/>
<%block name="head"><title>Articles</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/static/site.css">
<script src="/static/app.js" defer></script>
</%block>
<%block name="navigation">
  <nav>
    <h2>Browse topics</h2>
    ${topic_list(topic_index) | n}
  </nav>
</%block>

<%block name="content">
  <ul>
% for item in items:
    <li${' class="featured"' if item['featured'] else '' | n} data-category="${item['category']}"${' hidden' if item['draft'] else '' | n}>
      <!-- article ${item['id']} -->
      <img src="${item['thumbnail']}" alt="${item['title']}" width="64" height="64" loading="lazy">
      <a href="${item['url']}"${' target="_blank" rel="noopener"' if item['external'] else '' | n}>${item['title']}</a>
      <p>${item['summary']}</p>
% if item['featured']:
      <strong>Featured</strong>
% endif
      <span>${item['category']}</span>
      <span class="rating">${item['rating']}</span>
% if item['author']:
      <small><span>By ${item['author']}</span></small>
% endif
% if item['tags']:
      ${topic_list(item['tags']) | n}
% endif
% if item['comments']:
      <span>${item['comments']} comments</span>
% endif
    </li>
% endfor
  </ul>
</%block>
