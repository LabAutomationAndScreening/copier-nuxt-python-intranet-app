import { createHttpLink, from } from "@apollo/client/core";
import { onError } from "@apollo/client/link/error";
import { provideApolloClient } from "@vue/apollo-composable";

/**
 * See example: https://github.com/nuxt-modules/apollo/issues/442
 */
export default defineNuxtPlugin((nuxtApp) => {
  const { $apollo } = nuxtApp;

  // trigger the error hook on an error
  const errorLink = onError((err) => {
    nuxtApp.callHook("apollo:error", err); // must be called bc `@nuxtjs/apollo` will not do it anymore
  });

  // Default httpLink (main communication for apollo)
  const endpoint_uri = process.env.GRAPHQL_API_URL || "http://localhost:4000/graphql";
  console.log("Connecting to Backend API at:", endpoint_uri);
  const httpLink = createHttpLink({
    uri: endpoint_uri,
  });

  // Set custom links in the apollo client.
  // This is the link chain. Will be walked through from top to bottom. It can only contain 1 terminating
  // Apollo link, see: https://www.apollographql.com/docs/react/api/link/introduction/#the-terminating-link
  $apollo.defaultClient.setLink(from([errorLink, httpLink]));

  // For using useQuery in `@vue/apollo-composable`
  provideApolloClient($apollo.defaultClient);
});
