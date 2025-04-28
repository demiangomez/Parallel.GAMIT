export type UserState = {
    status: "unAuthorized" | "init";
    method: string;
};

export const initialState: UserState = {
    status: "init",
    method: "GET",
};

export type Action =
    | {
          type: "UNAUTHORIZE";
          method: string;
      }
    | {
          type: "INIT";
          method: string;
      };

export type Dispatch = (action: Action) => void;

export const useUserInfo = (state: UserState, action: Action): UserState => {
    switch (action.type) {
        case "INIT": {
            return {
                ...state,
                status: "init",
                method: action.method,
            };
        }
        case "UNAUTHORIZE": {
            return {
                ...state,
                status: "unAuthorized",
                method: action.method,
            };
        }
        default: {
            return state;
        }
    }
};
