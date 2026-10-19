import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { chat, getAssistantHealth, getAssistantHistory } from '../api/assistant';
import { errorMessage } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../context/AuthContext';
import { Alert, Button, Card, ErrorState, KeyValue, PageHeader, Spinner, StatusBadge } from '../components';
import { formatDateTime, humanize } from '../utils/format';

const SUGGESTIONS = [
  'Which materials are below reorder level?',
  'Which production jobs are overdue?',
  'Which jobs are awaiting quality inspection?',
  'Which deliveries are ready for dispatch?',
  'What is the procedure for handling a failed inspection?',
];

const SOURCE_TONE = { database: 'blue', documents: 'teal', none: 'grey' };

function Answer({ res }) {
  const { can } = useAuth();
  return (
    <>
      <div className="chat-meta">
        <StatusBadge status={res.source_type} label={`Source: ${humanize(res.source_type)}`} tone={SOURCE_TONE[res.source_type] || 'grey'} />
        <StatusBadge status={res.intent} label={humanize(res.intent)} tone="purple" />
        {res.grounded ? <StatusBadge status="grounded" label="Grounded" tone="green" /> : <StatusBadge status="ungrounded" label="Not grounded" tone="amber" />}
        {res.fallback_used ? <StatusBadge status="fallback" label="Fallback answer" tone="amber" /> : null}
        <span className="muted small">via {res.provider}</span>
      </div>
      <div className="chat-answer">{res.answer}</div>
      {res.facts?.length ? (
        <table className="table table-dense fact-table" style={{ marginTop: 12 }}>
          <tbody>{res.facts.map((f, i) => <tr key={i}><td>{f.label}</td><td>{f.value}</td></tr>)}</tbody>
        </table>
      ) : null}
      {res.citations?.length ? (
        <div className="citations">
          {res.citations.map((c) => (
            <div key={c.id} className="citation">
              <div className="citation-title">
                {can('documents:read') ? <Link to={`/documents/${c.document_id}`}>{c.document_title}</Link> : c.document_title}
              </div>
              <div className="muted small">
                {[`v${c.version_number}`, c.page_number ? `p. ${c.page_number}` : null, c.section].filter(Boolean).join(' · ')}
              </div>
              <div className="citation-excerpt">{c.excerpt}</div>
            </div>
          ))}
        </div>
      ) : null}
    </>
  );
}

export default function AssistantPage() {
  const history = useAsync(() => getAssistantHistory(), []);
  const health = useAsync(() => getAssistantHealth(), []);
  const [messages, setMessages] = useState([]); // {key, question, response?, error?, pending?}
  const [question, setQuestion] = useState('');
  const endRef = useRef(null);
  const pending = messages.some((m) => m.pending);

  useEffect(() => { endRef.current?.scrollIntoView?.({ block: 'end' }); }, [messages]);

  const ask = async (text) => {
    const q = text.trim();
    if (q.length < 2 || pending) return;
    const key = `${Date.now()}`;
    setQuestion('');
    setMessages((ms) => [...ms, { key, question: q, pending: true }]);
    try {
      const response = await chat(q);
      setMessages((ms) => ms.map((m) => (m.key === key ? { key, question: q, response } : m)));
    } catch (error) {
      setMessages((ms) => ms.map((m) => (m.key === key ? { key, question: q, error } : m)));
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(question); }
  };

  const past = [...(history.data || [])].reverse();
  const empty = !past.length && !messages.length;

  return (
    <>
      <PageHeader title="Assistant" subtitle="Ask about orders, inventory, production and approved documents. Answers cite their sources." />
      <div className="chat-layout">
        <Card>
          <div className="chat-thread" aria-live="polite">
            {history.error ? <Alert>{`Could not load history: ${errorMessage(history.error)}`}</Alert> : null}
            {history.loading && !history.data ? <Spinner /> : null}
            {past.map((h) => (
              <div key={`h-${h.id}`} className="stack-sm">
                <div className="chat-q">{h.question}</div>
                <div className="chat-msg chat-a">
                  <div className="chat-meta">
                    {h.intent ? <StatusBadge status={h.intent} label={humanize(h.intent)} tone="purple" /> : null}
                    <span className="muted small">{formatDateTime(h.created_at)}</span>
                  </div>
                  <div className="chat-answer">{h.answer}</div>
                </div>
              </div>
            ))}
            {messages.map((m) => (
              <div key={m.key} className="stack-sm">
                <div className="chat-q">{m.question}</div>
                <div className="chat-msg chat-a">
                  {m.pending ? <Spinner /> : m.error ? (
                    <Alert>{errorMessage(m.error)}</Alert>
                  ) : <Answer res={m.response} />}
                </div>
              </div>
            ))}
            {empty && !history.loading ? <p className="muted">No questions yet. Try one of the suggestions.</p> : null}
            <div ref={endRef} />
          </div>
          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); ask(question); }}>
            <textarea
              className="control"
              rows={2}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              maxLength={1000}
              placeholder="Ask a question… (Enter to send, Shift+Enter for a new line)"
              aria-label="Question"
            />
            <Button type="submit" variant="primary" icon="send" loading={pending} disabled={question.trim().length < 2}>Send</Button>
          </form>
        </Card>
        <div className="stack">
          <Card title="Status">
            {health.error ? <ErrorState error={health.error} onRetry={health.reload} title="Health unavailable" />
              : !health.data ? <Spinner /> : (
                <KeyValue items={[
                  ['Provider', health.data.provider],
                  ['LLM', health.data.llm_configured
                    ? <StatusBadge key="l" status="configured" label="Configured" tone="green" />
                    : <StatusBadge key="l" status="deterministic" label="Deterministic mode" tone="grey" />],
                  ['Retrieval', health.data.retrieval],
                ]} />
              )}
          </Card>
          <Card title="Try asking">
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="suggestion" disabled={pending} onClick={() => ask(s)}>{s}</button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
