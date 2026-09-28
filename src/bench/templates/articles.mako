<%def name="topic_list(topics)">
<div>
% for index, topic in enumerate(topics):
  <span>${topic}</span>${", " if index < len(topics) - 1 else ""}
% endfor
</div>
</%def>
<main>
  <nav>
    <h2>Browse topics</h2>
    ${topic_list(topic_index) | n}
  </nav>
  <ul>
% for item in items:
    <li>
      <a href="${item['url']}">${item['title']}</a>
      <p>${item['summary']}</p>
% if item['featured']:
      <strong>Featured</strong>
% endif
      <span>${item['category']}</span>
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
</main>
