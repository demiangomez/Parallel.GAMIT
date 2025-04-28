import { CountriesData, NetworkData, DropdownState } from "@types";
import { useState } from "react";


interface DropdownProps {
    position?: string;
    type: string;
    dropdown: DropdownState;
    data: any;
    dataSelected: string;
    setDataSelected: React.Dispatch<React.SetStateAction<string>>;
    setDropdown: React.Dispatch<React.SetStateAction<DropdownState>>;
}
const Dropdown = ({
    position,
    type,
    dropdown,
    data,
    dataSelected,
    setDataSelected,
    setDropdown,
}: DropdownProps) => {
    const [countryInput, setCountryInput] = useState("");
    const [networkInput, setNetworkInput] = useState("");

    const filteredCountriesData = data?.filter((country: CountriesData) => {
        if (countryInput !== "") {
            return (
                country?.three_digits_code
                    ?.toLowerCase()
                    .includes(countryInput?.toLowerCase()) ||
                country?.name
                    ?.toLowerCase()
                    .includes(countryInput?.toLowerCase())
            );
        }
    });

    const filteredNetworksData = data?.filter((nc: NetworkData) => {
        if (networkInput !== "") {
            return (
                nc?.network_code
                    ?.toLowerCase()
                    .includes(networkInput?.toLowerCase().trim()) ||
                nc?.network_name
                    ?.toLowerCase()
                    .includes(networkInput?.toLowerCase().trim())
            );
        }
    });

    const buttonStyles =
        position === "first"
            ? "whitespace-nowrap  h-full bg-gray-800 shadow-sm rounded-l-md flex items-center justify-center w-full px-4 py-2 text-sm font-medium text-white hover:bg-gray-50 hover:bg-gray-500 focus:outline-none"
            : "whitespace-nowrap  h-full bg-gray-800 shadow-sm flex items-center justify-center w-full px-4 py-2 text-sm font-medium text-white hover:bg-gray-50 hover:bg-gray-500 focus:outline-none";

    return (
        <div className="dropdown dropdown-end">
            <div
                tabIndex={0}
                role="button"
                className={buttonStyles}
                id="options-menu"
                title={"Select " + type}
                onClick={(event) => {
                    if (event.detail === 0) return;
                    setTimeout(() => {
                        setDropdown({
                            type: type,
                            dropdown: !dropdown.dropdown,
                        });
                    }, 50);
                }}
            >
                {type === "country" && !dataSelected
                    ? "CC"
                    : type === "networks" && !dataSelected
                      ? "NC"
                      : dataSelected}
                <svg
                    width="20"
                    height="20"
                    fill="currentColor"
                    viewBox="0 0 1792 1792"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <path d="M1408 704q0 26-19 45l-448 448q-19 19-45 19t-45-19l-448-448q-19-19-19-45t19-45 45-19h896q26 0 45 19t19 45z"></path>
                </svg>
            </div>
            {dropdown.dropdown &&
            dropdown?.type === "country" &&
            type === "country" ? (
                <ul
                    tabIndex={0}
                    className="dropdown-content z-30 p-2 shadow bg-gray-800 
                    max-h-[500px] overflow-y-auto sidebar scrollbar-thin scrollbar-webkit rounded-box w-52"
                >
                    <div className="text-white">
                        <input
                            type="text"
                            id="country-input"
                            autoComplete="off"
                            autoFocus
                            className="w-full h-16 peer placeholder-transparent mt-1
                      bg-transparent bg-clip-padding py-[0.25rem] pl-4 border-b-2
                    text-xl font-normal leading-[1.6] text-surface outline-none  transition
                    duration-200 ease-in-out focus:z-[3] focus:border-primary
                    focus:shadow-inset focus:outline-none motion-reduce:transition-none
                    autofill:shadow-autofill "
                            placeholder="Search Country"
                            aria-label="country"
                            aria-describedby="addon-wrapping"
                            onChange={(e) => setCountryInput(e.target.value)}
                        />
                        <label
                            htmlFor="country-input"
                            className="absolute left-1 -top-1 text-white text-xs mt-2 pointer-events-none
                        transition-all peer-placeholder-shown:text-base peer-placeholder-shown:top-2
                         peer-focus:-top-1 peer-focus:text-xs peer-focus:left-1 peer-placeholder-shown:left-1"
                        >
                            Search Country
                        </label>
                    </div>
                    <li>
                        {data && filteredCountriesData.length > 0
                            ? filteredCountriesData?.map(
                                  (code: CountriesData) => (
                                      <a
                                          key={code.id}
                                          className="flex items-center 
                                          justify-around py-2  
                                          hover:rounded-md  text-gray-100 
                                          hover:text-white hover:bg-gray-600 cursor-pointer"
                                          role="menuitem"
                                          onClick={() => {
                                              setDataSelected(
                                                  code.three_digits_code,
                                              );
                                              setDropdown({
                                                  dropdown: false,
                                                  type: undefined,
                                              });
                                          }}
                                      >
                                          <img
                                              width={50}
                                              height={50}
                                              src={`https://flagcdn.com/${code?.two_digits_code?.toLowerCase()}.svg`}
                                          />

                                          <strong>
                                              {code.three_digits_code}
                                          </strong>
                                      </a>
                                  ),
                              )
                            : data &&
                              filteredCountriesData.length <= 0 &&
                              data?.map(
                                  (code: CountriesData, index: number) => (
                                      <a
                                          key={code.id + "index" + index}
                                          className="flex items-center justify-around 
                                          py-2  hover:rounded-md 
                                           text-gray-100 hover:text-white
                                           hover:bg-gray-600 cursor-pointer"
                                          role="menuitem"
                                          onClick={() => {
                                              setDataSelected(
                                                  code.three_digits_code,
                                              );
                                              setDropdown({
                                                  dropdown: false,
                                                  type: undefined,
                                              });
                                          }}
                                      >
                                          <img
                                              width={50}
                                              height={50}
                                              src={`https://flagcdn.com/${code?.two_digits_code?.toLowerCase()}.svg`}
                                          />

                                          <strong>
                                              {code.three_digits_code}
                                          </strong>
                                      </a>
                                  ),
                              )}
                    </li>
                    {/* Aquí va el contenido del dropdown */}
                </ul>
            ) : (
                dropdown.dropdown &&
                dropdown?.type === "networks" &&
                type === "networks" && (
                    <ul
                        tabIndex={0}
                        className="dropdown-content z-30 p-2 shadow bg-gray-800 
                        max-h-[500px] overflow-y-auto sidebar scrollbar-thin scrollbar-webkit rounded-box w-52"
                    >
                        <div className="text-white">
                            <input
                                type="text"
                                id="network-code"
                                autoComplete="off"
                                autoFocus
                                className="w-full h-16 peer placeholder-transparent mt-1
                      bg-transparent bg-clip-padding py-[0.25rem] pl-4 border-b-2
                    text-xl font-normal leading-[1.6] text-surface outline-none  transition
                    duration-200 ease-in-out focus:z-[3] focus:border-primary
                    focus:shadow-inset focus:outline-none motion-reduce:transition-none
                    autofill:shadow-autofill "
                                placeholder="Search Network Code"
                                aria-label="Network Code"
                                aria-describedby="addon-wrapping"
                                onChange={(e) =>
                                    setNetworkInput(e.target.value)
                                }
                            />
                            <label
                                htmlFor="network-code"
                                className="absolute left-1 -top-1 text-white text-xs mt-2 pointer-events-none
                        transition-all peer-placeholder-shown:text-base peer-placeholder-shown:top-2
                         peer-focus:-top-1 peer-focus:text-xs peer-focus:left-1 peer-placeholder-shown:left-1"
                            >
                                Search Network Code
                            </label>
                        </div>
                        {data && filteredNetworksData.length > 0
                            ? filteredNetworksData
                                  ?.sort((a: NetworkData, b: NetworkData) => {
                                      if (a?.network_code?.includes("?"))
                                          return 1;
                                      if (b?.network_code?.includes("?"))
                                          return -1;

                                      return (
                                          a.network_code.localeCompare(
                                              b.network_code,
                                          ) ?? 0
                                      );
                                  })
                                  .map((n: NetworkData) => (
                                      <li key={n.network_code}>
                                          <a
                                              key={n?.api_id}
                                              className="flex items-center justify-center py-2
                                          hover:rounded-md 
                                          text-gray-100 hover:text-white
                                          hover:bg-gray-600 cursor-pointer"
                                              role="menuitem"
                                              onClick={() => {
                                                  setDataSelected(
                                                      n?.network_code?.toUpperCase(),
                                                  );
                                                  setDropdown({
                                                      dropdown: false,
                                                      type: undefined,
                                                  });
                                              }}
                                          >
                                              <strong>
                                                  {n?.network_code?.toUpperCase()}
                                              </strong>
                                          </a>
                                      </li>
                                  ))
                            : data &&
                              filteredNetworksData.length <= 0 &&
                              data
                                  ?.sort((a: NetworkData, b: NetworkData) => {
                                      if (a?.network_code?.includes("?"))
                                          return 1;
                                      if (b?.network_code?.includes("?"))
                                          return -1;
                                      return (
                                          a?.network_code?.localeCompare(
                                              b.network_code,
                                          ) ?? 0
                                      );
                                  })
                                  .map((n: NetworkData) => (
                                      <li key={n.network_code}>
                                          <a
                                              key={n?.api_id}
                                              className="flex items-center justify-center py-2
                                          hover:rounded-md 
                                          text-gray-100 hover:text-white
                                          hover:bg-gray-600 cursor-pointer"
                                              role="menuitem"
                                              onClick={() => {
                                                  setDataSelected(
                                                      n?.network_code?.toUpperCase(),
                                                  );
                                                  setDropdown({
                                                      dropdown: false,
                                                      type: undefined,
                                                  });
                                              }}
                                          >
                                              <strong>
                                                  {n?.network_code?.toUpperCase()}
                                              </strong>
                                          </a>
                                      </li>
                                  ))}
                    </ul>
                )
            )}
        </div>
    );
};

export default Dropdown;
