import { StationData } from "@types";
import { Link, useMatches } from "react-router-dom";

type Props = {
    state?: StationData;
};

const Breadcrumb = ({ state }: Props) => {
    // FAL: 05/08/2024
    // STATE IN BREADCRUMB REFERENCE TO STATION DATA BCS ITS USED IN MAIN PAGE
    // TO RETURN IT POSITION.

    const matches = useMatches();
    const crumbs = matches
        .filter((match: any) => Boolean(match.handle?.crumb))
        .map((match: any) => match.handle.crumb(match));

    return (
        <div
            className={`breadcrumbs absolute left-36 peer-[.w-72]:translate-x-40 transition-all mt-4 
                badge overflow-hidden text-sm`}
        >
            <ul>
                {crumbs.map((c: string, idx: number) => (
                    <li key={c + String(idx)}>
                        <Link to={`${matches[idx].pathname}`} state={state}>
                            {c}
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default Breadcrumb;
