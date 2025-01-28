// src/App.tsx
import { useEffect, useState, useCallback } from "react";
import { usePlaidLink } from "react-plaid-link";
import "./app.css";

interface PlaidLinkResponse {
  link_token: string;
  user_id: string;
}

interface Transaction {
  account_id: string;
  amount: number;
  date: string;
  name: string;
  merchant_name?: string;
  payment_channel: string;
  pending: boolean;
  transaction_id: string;
}

interface LinkProps {
  linkToken: string;
  onAccessTokenReceived: (token: string) => void;
}

const Link: React.FC<LinkProps> = ({ linkToken, onAccessTokenReceived }) => {
  const onSuccess = useCallback(
    async (public_token: string) => {
      try {
        const response = await fetch(
          "http://localhost:8000/api/exchange_token",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ public_token }),
          }
        );

        if (!response.ok) {
          throw new Error("Failed to exchange token");
        }

        const data = await response.json();
        onAccessTokenReceived(data.access_token);
      } catch (error) {
        console.error("Error exchanging public token:", error);
      }
    },
    [onAccessTokenReceived]
  );

  const config = {
    token: linkToken,
    onSuccess,
  };

  const { open, ready } = usePlaidLink(config);

  return (
    <button onClick={() => open()} disabled={!ready} className="connect-button">
      Connect your bank account
    </button>
  );
};

function App() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateToken = async () => {
    try {
      const response = await fetch(
        "http://localhost:8000/api/create_link_token",
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to create link token");
      }

      const data = await response.json();
      setLinkToken(data.link_token);
    } catch (error) {
      console.error("Error getting link token:", error);
      setError("Failed to initialize Plaid Link");
    }
  };

  useEffect(() => {
    generateToken();
  }, []);

  const getTransactions = async () => {
    if (!accessToken) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:8000/api/transactions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ access_token: accessToken }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch transactions");
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      setTransactions(data.latest_transactions);
    } catch (error) {
      console.error("Error fetching transactions:", error);
      setError("Failed to fetch transactions. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  if (error) {
    return (
      <div className="container">
        <div className="error-message">{error}</div>
        <button onClick={generateToken} className="retry-button">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Plaid Integration Demo</h1>

        {!accessToken ? (
          linkToken && (
            <Link
              linkToken={linkToken}
              onAccessTokenReceived={setAccessToken}
            />
          )
        ) : (
          <div className="success-section">
            <div className="success-message">
              ✓ Bank account connected successfully
            </div>
            <button
              onClick={getTransactions}
              className="transactions-button"
              disabled={loading}
            >
              {loading ? "Loading transactions..." : "Get Transactions"}
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-message">
            Syncing your transactions... This may take a moment.
          </div>
        )}

        {transactions.length > 0 && (
          <div className="transactions-section">
            <h2>Recent Transactions</h2>
            <div className="transactions-list">
              {transactions.map((transaction) => (
                <div
                  key={transaction.transaction_id}
                  className="transaction-item"
                >
                  <div className="transaction-header">
                    <div className="transaction-name">
                      {transaction.merchant_name || transaction.name}
                    </div>
                    <div className="transaction-amount">
                      ${Math.abs(transaction.amount).toFixed(2)}
                    </div>
                  </div>
                  <div className="transaction-details">
                    <div className="transaction-date">
                      {formatDate(transaction.date)}
                    </div>
                    {transaction.pending && (
                      <div className="transaction-pending">Pending</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
