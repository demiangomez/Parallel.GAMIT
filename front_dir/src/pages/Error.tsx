import { Link } from "react-router-dom";

const Error = () => {
    return (
        <div className="hero my-auto bg-inherit">
            <div className="hero-content text-center">
                <div className="max-w-[700px]">
                    <h1 className="text-9xl font-bold">404</h1>
                    <h2 className="text-5xl font-semibold">
                        Something is missing.
                    </h2>
                    <p className="text-xl py-6">
                        Sorry, we can't find that page. You'll find lots to
                        explore on the home page.
                    </p>
                    <Link to="/" role="button" className="btn btn-secondary">
                        Back to homepage
                    </Link>
                </div>
            </div>
        </div>
    );
};

export default Error;
